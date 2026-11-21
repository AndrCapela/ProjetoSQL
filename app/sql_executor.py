"""Executor seguro e somente leitura para consultas SQL em SQLite e DuckDB."""

from __future__ import annotations

import datetime
import math
import re
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb

from app.database import (
    DEFAULT_DB_PATH,
    DEFAULT_DUCKDB_PATH,
    connect_duckdb_readonly,
    ensure_database,
)
from app.schemas import DatabaseEngine

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

DUCKDB_ALLOWED_START_KEYWORDS = {
    "SELECT",
    "WITH",
    "FROM",
    "PIVOT",
    "UNPIVOT",
    "DESCRIBE",
    "SHOW",
    "SUMMARIZE",
    "VALUES",
}

DUCKDB_FORBIDDEN_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
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
    "COPY",
    "EXPORT",
    "IMPORT",
    "CALL",
    "SET",
    "RESET",
    "INSTALL",
    "LOAD",
    "USE",
    "CHECKPOINT",
    "FORCE",
    "MERGE",
    "GRANT",
    "REVOKE",
    "COMMENT",
    "PREPARE",
    "EXECUTE",
    "DEALLOCATE",
    "ANALYZE",
    "EXPLAIN",
}

DUCKDB_BLOCKED_FUNCTIONS = {
    "READ_CSV",
    "READ_CSV_AUTO",
    "READ_PARQUET",
    "READ_JSON",
    "READ_JSON_AUTO",
    "READ_TEXT",
    "READ_BLOB",
    "GLOB",
    "SNIFF_CSV",
    "PARQUET_SCAN",
    "PARQUET_METADATA",
    "PARQUET_SCHEMA",
    "SQLITE_SCAN",
    "SQLITE_ATTACH",
    "POSTGRES_SCAN",
    "MYSQL_SCAN",
    "ICEBERG_SCAN",
    "DELTA_SCAN",
    "CURRENT_SETTING",
    "DUCKDB_SETTINGS",
    "DUCKDB_EXTENSIONS",
    "DUCKDB_DATABASES",
    "DUCKDB_SECRETS",
    "DUCKDB_MEMORY",
    "DUCKDB_TEMPORARY_FILES",
    "DUCKDB_VARIABLES",
    "DUCKDB_LOGS",
    "DUCKDB_LOG_CONTEXTS",
    "PRAGMA_DATABASE_LIST",
    "PRAGMA_PLATFORM",
    "PRAGMA_VERSION",
    "PRAGMA_USER_AGENT",
    "WHICH_SECRET",
    "GETENV",
}

_DOLLAR_TAG_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)?\$")


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


def _strip_comments_and_strings(
    sql: str,
    allow_bracket_identifiers: bool = True,
    allow_dollar_strings: bool = False,
    allow_nested_comments: bool = False,
) -> str:
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

        # Comentário em bloco /* ... */ (com suporte opcional a aninhamento no DuckDB)
        if ch == "/" and nxt == "*":
            i += 2
            depth = 1
            while i < length and depth > 0:
                if allow_nested_comments and sql[i] == "/" and i + 1 < length and sql[i + 1] == "*":
                    depth += 1
                    i += 2
                    continue
                if sql[i] == "*" and i + 1 < length and sql[i + 1] == "/":
                    depth -= 1
                    i += 2
                    continue
                i += 1
            out.append(" ")
            continue

        # String delimitada por cifrão $$...$$ ou $tag$...$tag$ (DuckDB / PostgreSQL)
        if allow_dollar_strings and ch == "$":
            tag_match = _DOLLAR_TAG_RE.match(sql, i)
            if tag_match:
                tag = tag_match.group(0)
                end_pos = sql.find(tag, tag_match.end())
                if end_pos == -1:
                    i = length
                else:
                    i = end_pos + len(tag)
                out.append(" __LITERAL__ ")
                continue

        # Literal de texto '...', identificador "..." ou crase `...`
        if ch in ("'", '"', "`"):
            quote = ch
            is_escape_literal = (
                allow_dollar_strings
                and quote == "'"
                and i > 0
                and sql[i - 1] in ("e", "E")
                and (i == 1 or not (sql[i - 2].isalnum() or sql[i - 2] == "_"))
            )
            i += 1
            while i < length:
                if is_escape_literal and sql[i] == "\\":
                    i += 2
                    continue
                if sql[i] == quote:
                    if i + 1 < length and sql[i + 1] == quote:
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            out.append(" __LITERAL__ ")
            continue

        # Identificador entre colchetes [...] no padrão SQLite (desabilitado no DuckDB por ser lista)
        if allow_bracket_identifiers and ch == "[":
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


def validate_readonly_sql(sql: str, engine: DatabaseEngine = "sqlite") -> str:
    """Valida que a query é uma única consulta somente leitura segura e retorna o SQL limpo."""
    if not sql or not sql.strip():
        raise SQLValidationError("Digite uma consulta SQL antes de executar.")

    is_duckdb = engine == "duckdb"
    cleaned = sql.strip()
    sanitized = _strip_comments_and_strings(
        cleaned,
        allow_bracket_identifiers=not is_duckdb,
        allow_dollar_strings=is_duckdb,
        allow_nested_comments=is_duckdb,
    ).strip()

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

    if is_duckdb:
        if tokens[0] not in DUCKDB_ALLOWED_START_KEYWORDS:
            raise SQLValidationError(
                "No DuckDB (Friendly SQL), apenas consultas de leitura (SELECT, WITH, FROM, PIVOT, DESCRIBE, SUMMARIZE) são permitidas."
            )
        blocked = [tok for tok in tokens if tok in DUCKDB_FORBIDDEN_KEYWORDS]
        if blocked:
            raise SQLValidationError(
                f"Comando não permitido em modo somente leitura: {blocked[0]}."
            )
        blocked_fns = [tok for tok in tokens if tok in DUCKDB_BLOCKED_FUNCTIONS]
        if blocked_fns:
            raise SQLValidationError(
                f"Função bloqueada em modo somente leitura isolado: {blocked_fns[0]}."
            )
    else:
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
    """Converte tipos SQLite/DuckDB incompatíveis com JSON (Decimal, date, Inf/NaN, bytes) com segurança."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        fval = float(value)
        if not math.isfinite(fval):
            raise SQLValidationError(
                "A consulta gerou um valor numérico infinito ou indefinido (Inf/NaN), que não pode ser exibido."
            )
        return fval
    if isinstance(value, float):
        if not math.isfinite(value):
            raise SQLValidationError(
                "A consulta gerou um valor numérico infinito ou indefinido (Inf/NaN), que não pode ser exibido."
            )
        return value
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, (datetime.timedelta, uuid.UUID)):
        return str(value)
    if isinstance(value, str):
        if len(value.encode("utf-8")) > MAX_SQLITE_VALUE_BYTES:
            raise SQLValidationError(
                "O valor de texto gerado pela consulta excedeu o limite máximo permitido."
            )
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        raw = bytes(value)
        hex_preview = raw[:64].hex().upper()
        suffix = "..." if len(raw) > 64 else ""
        return f"X'{hex_preview}{suffix}'"
    if isinstance(value, (list, tuple)):
        return [_sanitize_cell(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _sanitize_cell(v) for k, v in value.items()}
    return value


def _run_sqlite_query(
    sql_to_run: str,
    db_path: Path,
    max_rows: int,
    timeout_seconds: float,
) -> SQLExecutionResult:
    """Executa uma consulta em conexão SQLite somente leitura com timeout e limite."""
    ensure_database(db_path, engine="sqlite")

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


def _run_duckdb_query(
    sql_to_run: str,
    db_path: Path,
    max_rows: int,
    timeout_seconds: float,
) -> SQLExecutionResult:
    """Executa uma consulta em conexão DuckDB somente leitura com sandbox e timeout."""
    ensure_database(db_path, engine="duckdb")
    conn = connect_duckdb_readonly(db_path)
    start_time = time.perf_counter()
    timed_out = threading.Event()

    def _interrupt_query() -> None:
        timed_out.set()
        try:
            conn.interrupt()
        except Exception:
            pass

    timer = threading.Timer(timeout_seconds, _interrupt_query)
    timer.daemon = True
    timer.start()

    try:
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
    except duckdb.Error as exc:
        if timed_out.is_set() or "interrupt" in str(exc).lower():
            raise TimeoutError(
                f"A consulta excedeu o tempo limite de {timeout_seconds:.1f}s e foi interrompida."
            ) from exc
        raise
    finally:
        timer.cancel()
        conn.close()


def execute_readonly_sql(
    sql: str,
    db_path: Path | None = None,
    max_rows: int = MAX_ROWS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    engine: DatabaseEngine = "sqlite",
) -> SQLExecutionResult:
    """Executa uma consulta somente leitura em SQLite ou DuckDB com timeout e limite de linhas."""
    cleaned_sql = validate_readonly_sql(sql, engine=engine)
    if engine == "duckdb":
        target = db_path if db_path is not None else DEFAULT_DUCKDB_PATH
        return _run_duckdb_query(cleaned_sql, target, max_rows, timeout_seconds)
    target = db_path if db_path is not None else DEFAULT_DB_PATH
    return _run_sqlite_query(cleaned_sql, target, max_rows, timeout_seconds)


def explain_readonly_sql(
    sql: str,
    db_path: Path | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    engine: DatabaseEngine = "sqlite",
) -> SQLExecutionResult:
    """Retorna o plano de execução de uma consulta somente leitura válida."""
    cleaned_sql = validate_readonly_sql(sql, engine=engine)
    if engine == "duckdb":
        target = db_path if db_path is not None else DEFAULT_DUCKDB_PATH
        return _run_duckdb_query(f"EXPLAIN {cleaned_sql}", target, MAX_ROWS, timeout_seconds)
    target = db_path if db_path is not None else DEFAULT_DB_PATH
    return _run_sqlite_query(
        f"EXPLAIN QUERY PLAN {cleaned_sql}",
        target,
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


def translate_duckdb_error(error_msg: str) -> str | None:
    """Traduz erros comuns do DuckDB em dicas didáticas em português."""
    msg = error_msg.strip()
    lower = msg.lower()

    if match := re.search(r'ambiguous reference to column name\s+"?([^"\n]+?)"?(?:\s|$)', msg, re.IGNORECASE):
        col = match.group(1)
        return (
            f"Dica: a coluna '{col}' existe em mais de uma tabela do JOIN. "
            f"Use o apelido da tabela (ex.: a.{col})."
        )

    if match := re.search(r'referenced column\s+"([^"]+)"\s+not found', msg, re.IGNORECASE):
        col = match.group(1)
        return (
            f"Dica: a coluna '{col}' não foi encontrada nessa tabela/consulta. Confira o nome no esquema ao lado; "
            "textos literais devem ficar entre aspas simples: 'valor'."
        )

    if match := re.search(r'table with name\s+(\S+)\s+does not exist', msg, re.IGNORECASE):
        tbl = match.group(1)
        return (
            f"Dica: a tabela '{tbl}' não existe. As tabelas disponíveis são: "
            "professores, cursos, disciplinas, alunos, alunos_disciplinas e notas."
        )

    if "combining qualify with group by all" in lower:
        return (
            "Dica: o DuckDB ainda não permite combinar QUALIFY com GROUP BY ALL na mesma consulta. "
            "Liste as colunas explícitas no GROUP BY (ex.: GROUP BY a.id, a.nome) ao usar QUALIFY."
        )

    if "window function calls cannot be nested" in lower or "where clause cannot contain window functions" in lower:
        return (
            "Dica: funções de janela (RANK, DENSE_RANK, AVG() OVER) não podem ir no WHERE. "
            "No Friendly SQL do DuckDB, use a cláusula QUALIFY logo após o FROM/WHERE!"
        )

    if "where clause cannot contain aggregates" in lower:
        return (
            "Dica: funções de agregação (COUNT, AVG, SUM, MIN, MAX) não podem ir no WHERE. "
            "Use GROUP BY ALL + HAVING."
        )

    if "must appear in the group by clause" in lower:
        return (
            "Dica: há colunas no SELECT fora de funções de agregação que não estão no GROUP BY. "
            "No DuckDB Friendly SQL, você pode simplesmente usar GROUP BY ALL!"
        )

    if match := re.search(r'(?:scalar|aggregate|table)?\s*function with name\s+(\S+)\s+does not exist', msg, re.IGNORECASE):
        fn = match.group(1)
        return (
            f"Dica: a função '{fn}' não foi encontrada no DuckDB. "
            "Confira o 'Guia SQL' no topo para ver as funções disponíveis (ex.: strftime, YEAR, COUNT_IF, BOOL_AND)."
        )

    if "parser error" in lower or "syntax error" in lower:
        return (
            "Dica: erro de sintaxe no DuckDB. Verifique aspas simples para textos, parênteses fechados "
            "e a estrutura das cláusulas (no Friendly SQL você pode começar com FROM ou SELECT, e filtrar window functions com QUALIFY)."
        )

    if "no function matches the given name and argument types 'strftime" in lower:
        return (
            "Dica: no DuckDB os argumentos de strftime são invertidos em relação ao SQLite: "
            "strftime(data, '%Y') — ou simplesmente use YEAR(data)."
        )

    if "conversion error" in lower or "could not convert" in lower or "cannot compare values of type" in lower:
        return (
            "Dica: erro de conversão/comparação de tipos no DuckDB (ex.: comparar data com número; "
            "para datas use DATE 'YYYY-MM-DD' ou funções como YEAR(coluna))."
        )

    if "permission error" in lower or "disabled by configuration" in lower or "read-only mode" in lower:
        return (
            "Dica: operação bloqueada porque o ambiente executa DuckDB isolado em modo somente leitura."
        )

    return None


def translate_sql_error(error_msg: str, engine: DatabaseEngine = "sqlite") -> str | None:
    """Seleciona o tradutor de erros didáticos correspondente ao motor SQL."""
    if engine == "duckdb":
        return translate_duckdb_error(error_msg)
    return translate_sqlite_error(error_msg)
