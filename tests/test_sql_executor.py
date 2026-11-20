"""Testes de segurança, validação somente leitura e limites do executor SQL."""

from pathlib import Path

import pytest

from app.database import create_and_seed_database
from app.sql_executor import (
    SQLValidationError,
    execute_readonly_sql,
    translate_sqlite_error,
    validate_readonly_sql,
)


@pytest.fixture()
def seeded_db(tmp_path: Path) -> Path:
    return create_and_seed_database(tmp_path / "exec.db", overwrite=True)


def test_valid_select_and_cte_queries(seeded_db: Path) -> None:
    res = execute_readonly_sql(
        "SELECT nome, idade FROM alunos WHERE idade > 30;",
        db_path=seeded_db,
    )
    assert res.columns == ["nome", "idade"]
    assert res.row_count > 0
    assert all(row[1] > 30 for row in res.rows)

    cte_res = execute_readonly_sql(
        "WITH maiores AS (SELECT id, nome FROM alunos WHERE idade > 35) SELECT nome FROM maiores;",
        db_path=seeded_db,
    )
    assert cte_res.columns == ["nome"]
    assert cte_res.row_count > 0


def test_allows_forbidden_words_inside_string_literals(seeded_db: Path) -> None:
    res = execute_readonly_sql(
        "SELECT 'DROP TABLE alunos; DELETE' AS aviso;",
        db_path=seeded_db,
    )
    assert res.rows == [["DROP TABLE alunos; DELETE"]]


@pytest.mark.parametrize(
    "bad_sql",
    [
        "",
        "   ",
        "DROP TABLE alunos;",
        "DELETE FROM alunos WHERE id = 1;",
        "INSERT INTO cursos (nome, categoria, carga_horaria) VALUES ('X', 'Y', 10);",
        "UPDATE alunos SET idade = 99;",
        "PRAGMA table_info(alunos);",
        "ATTACH DATABASE 'x.db' AS hack;",
        "SELECT * FROM alunos; DROP TABLE alunos;",
        "-- comentario\nDELETE FROM notas;",
        "/* bloco */ UPDATE professores SET salario = 1;",
    ],
)
def test_blocks_unsafe_or_non_select_sql(bad_sql: str) -> None:
    with pytest.raises(SQLValidationError):
        validate_readonly_sql(bad_sql)


def test_row_limit_truncation(seeded_db: Path) -> None:
    res = execute_readonly_sql(
        "SELECT id FROM notas;",
        db_path=seeded_db,
        max_rows=10,
    )
    assert res.row_count == 10
    assert res.truncated is True


def test_timeout_interrupts_heavy_recursive_query(seeded_db: Path) -> None:
    heavy_sql = """
    WITH RECURSIVE loop(x) AS (
        SELECT 1
        UNION ALL
        SELECT x + 1 FROM loop
    )
    SELECT COUNT(*) FROM loop;
    """
    with pytest.raises(TimeoutError):
        execute_readonly_sql(heavy_sql, db_path=seeded_db, timeout_seconds=0.05)


@pytest.mark.parametrize(
    ("raw_error", "expected_snippet"),
    [
        ("ambiguous column name: id", "apelido"),
        ("no such column: aluno_nome", "aspas simples"),
        ("no such table: turma", "professores"),
        ("misuse of aggregate: AVG()", "HAVING"),
        ('near "FROM": syntax error', "sintaxe"),
        ("no such function: YEAR", "Guia SQL"),
    ],
)
def test_translate_sqlite_error_returns_friendly_hints(
    raw_error: str, expected_snippet: str
) -> None:
    hint = translate_sqlite_error(raw_error)
    assert hint is not None
    assert expected_snippet.lower() in hint.lower()


def test_translate_sqlite_error_returns_none_for_unknown() -> None:
    assert translate_sqlite_error("erro desconhecido qualquer") is None
