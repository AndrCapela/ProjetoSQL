"""Executor seguro e somente leitura para consultas SQL em SQLite."""

from __future__ import annotations

import math
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.database import DEFAULT_DB_PATH, ensure_database

MAX_ROWS = 500
MAX_SQLITE_VALUE_BYTES = 100_000
DEFAULT_TIMEOUT_SECONDS = 1.5

BLOCKED_SQL_FUNCTIONS = {
    "LOAD_EXTENSION",
    "FTS3_TOKENIZER",
    "ZEROBLOB",
    "RANDOMBLOB",
}

FORBIDDEN_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "REPLACE",
    "TRUNCATE",
    "ATTACH",
    "DETACH",
    "PRAGMA",
    "VACUUM",
    "REINDEX",
    "BEGIN",
    "COMMIT",
    "ROLLBACK",
    "SAVEPOINT",
    "RELEASE",
}


class SQLValidationError(ValueError):
    """Erro lançado quando a query viola as regras de segurança somente leitura."""


@dataclass(frozen=True)
class SQLExecutionResult:
    """Resultado estruturado da execução de uma consulta SQL."""

    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    execution_ms: float
    truncated: bool = False


def _strip_comments_and_strings(sql: str) -> str:
    """Remove comentários e conteúdo de literais para validação segura de palavras-chave."""
    out: list[str] = []
    i = 0
    length = len(sql)

    while i < length:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < length else ""

        # Comentário de linha -- ...
        if ch == "-" and nxt == "-":
            i += 2
            while i < length and sql[i] != "\n":
                i += 1
            out.append(" ")
            continue

        # Comentário em bloco /* ... */
        if ch == "/" and nxt == "*":
            i += 2
            while i + 1 < length and not (sql[i] == "*" and sql[i + 1] == "/"):
                i += 1
            i += 2
            out.append(" ")
            continue

        # Literal de texto '...', identificador "..." ou crase `...`
        if ch in ("'", '"', "`"):
            quote = ch
            i += 1
            while i < length:
                if sql[i] == quote:
                    if i + 1 < length and sql[i + 1] == quote:
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            out.append(" __LITERAL__ ")
            continue

        # Identificador entre colchetes [...] no padrão SQLite
        if ch == "[":
            i += 1
            while i < length and sql[i] != "]":
                i += 1
            if i < length:
                i += 1
            out.append(" __LITERAL__ ")
            continue

        out.append(ch)
        i += 1

    return "".join(out)


def validate_readonly_sql(sql: str) -> str:
    """Valida que a query é uma única consulta SELECT/WITH segura e retorna o SQL limpo."""
    if not sql or not sql.strip():
        raise SQLValidationError("Digite uma consulta SQL antes de executar.")

    cleaned = sql.strip()
    sanitized = _strip_comments_and_strings(cleaned).strip()

    if not sanitized:
        raise SQLValidationError("A consulta não contém comandos SQL válidos.")

    # Permite um único ';' final, mas bloqueia múltiplos statements.
    if sanitized.endswith(";"):
        sanitized_body = sanitized[:-1].strip()
        if cleaned.endswith(";"):
            cleaned = cleaned[:-1].strip()
    else:
        sanitized_body = sanitized

    if not sanitized_body:
        raise SQLValidationError("A consulta SQL está vazia.")

    if ";" in sanitized_body:
        raise SQLValidationError("Apenas uma única consulta SQL por execução é permitida.")

    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", sanitized_body.upper())
    if not tokens:
        raise SQLValidationError("Não foi possível identificar um comando SQL válido.")

    if tokens[0] not in {"SELECT", "WITH"}:
        raise SQLValidationError(
            "Apenas consultas de leitura iniciadas com SELECT ou WITH são permitidas."
        )

    blocked = [tok for tok in tokens if tok in FORBIDDEN_KEYWORDS]
    if blocked:
        raise SQLValidationError(
            f"Comando não permitido em modo somente leitura: {blocked[0]}."
        )

    return cleaned


def _sql_authorizer(
    action: int,
    arg1: str | None,
    arg2: str | None,
    db_name: str | None,
    trigger_name: str | None,
) -> int:
    """Autorizador SQLite em lista branca para garantir execução somente leitura."""
    if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ):
        return sqlite3.SQLITE_OK
    if hasattr(sqlite3, "SQLITE_RECURSIVE") and action == sqlite3.SQLITE_RECURSIVE:
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_FUNCTION:
        if arg2 and arg2.upper() in BLOCKED_SQL_FUNCTIONS:
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def _sanitize_cell(value: Any) -> Any:
    """Converte tipos SQLite incompatíveis com JSON (Inf/NaN/bytes) com segurança."""
    if isinstance(value, float) and not math.isfinite(value):
        raise SQLValidationError(
            "A consulta gerou um valor numérico infinito ou indefinido (Inf/NaN), que não pode ser exibido."
        )
    if isinstance(value, (bytes, bytearray, memoryview)):
        raw = bytes(value)
        hex_preview = raw[:64].hex().upper()
        suffix = "..." if len(raw) > 64 else ""
        return f"X'{hex_preview}{suffix}'"
    return value


def _run_sqlite_query(
    sql_to_run: str,
    db_path: Path,
    max_rows: int,
    timeout_seconds: float,
) -> SQLExecutionResult:
    """Executa uma consulta em conexão SQLite somente leitura com timeout e limite."""
    ensure_database(db_path)

    conn = sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True)
    start_time = time.perf_counter()

    def _progress_handler() -> int:
        if (time.perf_counter() - start_time) > timeout_seconds:
            return 1
        return 0

    try:
        conn.execute("PRAGMA query_only = ON;")
        if hasattr(conn, "setlimit") and hasattr(sqlite3, "SQLITE_LIMIT_LENGTH"):
            conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_SQLITE_VALUE_BYTES)
        conn.set_authorizer(_sql_authorizer)
        conn.set_progress_handler(_progress_handler, 5_000)

        cursor = conn.execute(sql_to_run)
        columns = [desc[0] for desc in (cursor.description or [])]
        fetched = cursor.fetchmany(max_rows + 1)

        truncated = len(fetched) > max_rows
        rows = [[_sanitize_cell(cell) for cell in row] for row in fetched[:max_rows]]
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return SQLExecutionResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            execution_ms=elapsed_ms,
            truncated=truncated,
        )
    except sqlite3.OperationalError as exc:
        if "interrupted" in str(exc).lower():
            raise TimeoutError(
                f"A consulta excedeu o tempo limite de {timeout_seconds:.1f}s e foi interrompida."
            ) from exc
        raise
    finally:
        conn.set_progress_handler(None, 0)
        conn.set_authorizer(None)
        conn.close()


def execute_readonly_sql(
    sql: str,
    db_path: Path = DEFAULT_DB_PATH,
    max_rows: int = MAX_ROWS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> SQLExecutionResult:
    """Executa uma consulta SELECT/WITH em SQLite somente leitura com timeout e limite de linhas."""
    cleaned_sql = validate_readonly_sql(sql)
    return _run_sqlite_query(cleaned_sql, db_path, max_rows, timeout_seconds)


def explain_readonly_sql(
    sql: str,
    db_path: Path = DEFAULT_DB_PATH,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> SQLExecutionResult:
    """Retorna o plano de execução (EXPLAIN QUERY PLAN) de uma consulta SELECT/WITH válida."""
    cleaned_sql = validate_readonly_sql(sql)
    return _run_sqlite_query(
        f"EXPLAIN QUERY PLAN {cleaned_sql}",
        db_path,
        MAX_ROWS,
        timeout_seconds,
    )


def translate_sqlite_error(error_msg: str) -> str | None:
    """Traduz erros comuns do SQLite em dicas didáticas em português para iniciantes."""
    msg = error_msg.strip()
    lower = msg.lower()

    if match := re.search(r"ambiguous column name:\s*(\S+)", msg, re.IGNORECASE):
        col = match.group(1)
        return (
            f"Dica: a coluna '{col}' existe em mais de uma tabela do JOIN. "
            f"Especifique qual tabela usar com um apelido (ex.: a.{col})."
        )

    if match := re.search(r"no such column:\s*(\S+)", msg, re.IGNORECASE):
        col = match.group(1)
        return (
            f"Dica: a coluna '{col}' não foi encontrada. Confira o nome exato no esquema ao lado; "
            "se for um texto literal (como uma cidade ou status), coloque entre aspas simples: 'valor'."
        )

    if match := re.search(r"no such table:\s*(\S+)", msg, re.IGNORECASE):
        tbl = match.group(1)
        return (
            f"Dica: a tabela '{tbl}' não existe. As tabelas disponíveis são: "
            "professores, cursos, disciplinas, alunos, alunos_disciplinas e notas."
        )

    if "misuse of aggregate" in lower:
        return (
            "Dica: funções de agregação (COUNT, AVG, SUM, MIN, MAX) não podem ir no WHERE. "
            "Use GROUP BY + HAVING ou envolva a agregação em uma subquery/CTE."
        )

    if "syntax error" in lower:
        return (
            "Dica: erro de sintaxe SQL. Verifique vírgulas sobrando antes do FROM, parênteses ou aspas "
            "não fechadas e a ordem das cláusulas (SELECT → FROM → JOIN → WHERE → GROUP BY → HAVING → ORDER BY → LIMIT)."
        )

    if match := re.search(r"no such function:\s*(\S+)", msg, re.IGNORECASE):
        fn = match.group(1)
        return (
            f"Dica: a função '{fn}' não existe no SQLite. Abra o 'Guia SQL' no topo para conferir "
            "equivalentes no SQLite (ex.: strftime('%Y', data) no lugar de YEAR)."
        )

    if "wrong number of arguments to function" in lower:
        return (
            "Dica: quantidade incorreta de argumentos na função chamada "
            "(ex.: ROUND(valor, 2) ou strftime('%Y', coluna))."
        )

    if "order by term out of range" in lower:
        return (
            "Dica: o número usado no ORDER BY é maior que a quantidade de colunas do SELECT."
        )

    if "do not have the same number of result columns" in lower:
        return (
            "Dica: em UNION / UNION ALL, todas as consultas devem retornar o mesmo número de colunas."
        )

    if "string or blob too big" in lower:
        return (
            "Dica: o valor de texto/blob gerado pela consulta excedeu o limite máximo permitido."
        )

    if "not authorized" in lower:
        return (
            "Dica: a consulta utilizou uma função ou operação não autorizada em modo somente leitura."
        )

    return None
