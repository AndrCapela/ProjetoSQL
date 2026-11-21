"""Testes de segurança, validação somente leitura e limites do executor SQL."""

import sqlite3
from pathlib import Path

import duckdb

import pytest

from app.database import (
    connect_duckdb_readonly,
    create_and_seed_database,
    create_and_seed_duckdb,
)
from app.sql_executor import (
    SQLValidationError,
    execute_readonly_sql,
    explain_readonly_sql,
    translate_duckdb_error,
    translate_sql_error,
    translate_sqlite_error,
    validate_readonly_sql,
)


@pytest.fixture()
def seeded_db(tmp_path: Path) -> Path:
    return create_and_seed_database(tmp_path / "exec.db", overwrite=True)


@pytest.fixture()
def seeded_duckdb(tmp_path: Path) -> Path:
    return create_and_seed_duckdb(tmp_path / "exec.duckdb", overwrite=True)


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


def test_allows_bracket_and_backtick_identifiers_and_sanitizes_values(seeded_db: Path) -> None:
    res_ident = execute_readonly_sql(
        "SELECT [a;b], `delete` FROM (SELECT 1 AS [a;b], 2 AS `delete`);",
        db_path=seeded_db,
    )
    assert res_ident.rows == [[1, 2]]

    res_blob = execute_readonly_sql("SELECT X'ff00ab' AS raw_val;", db_path=seeded_db)
    assert res_blob.rows == [["X'FF00AB'"]]

    with pytest.raises(SQLValidationError):
        execute_readonly_sql("SELECT 1e999;", db_path=seeded_db)


def test_authorizer_blocks_zeroblob_and_allows_explain(seeded_db: Path) -> None:
    with pytest.raises(sqlite3.DatabaseError):
        execute_readonly_sql("SELECT zeroblob(1000);", db_path=seeded_db)

    plan = explain_readonly_sql(
        "SELECT d.nome, p.nome FROM disciplinas d JOIN professores p ON p.id = d.professor_id;",
        db_path=seeded_db,
    )
    assert plan.row_count >= 1
    assert any("SEARCH" in " ".join(str(c) for c in row) for row in plan.rows)


def test_duckdb_friendly_sql_features(seeded_duckdb: Path) -> None:
    # FROM-first + ORDER BY ALL
    res_from = execute_readonly_sql(
        "FROM alunos SELECT DISTINCT cidade ORDER BY ALL;",
        db_path=seeded_duckdb,
        engine="duckdb",
    )
    assert res_from.columns == ["cidade"]
    assert res_from.row_count > 1

    # GROUP BY ALL + COUNT_IF + BOOL_AND
    res_agg = execute_readonly_sql(
        """
        FROM alunos_disciplinas
        SELECT
            status,
            COUNT(*) AS total,
            COUNT_IF(status = 'concluida') AS qtd_concluidas
        GROUP BY ALL
        ORDER BY total DESC, status ASC;
        """,
        db_path=seeded_duckdb,
        engine="duckdb",
    )
    assert res_agg.row_count == 3

    # QUALIFY + ANTI JOIN + PIVOT + EXCLUDE/REPLACE + SUMMARIZE + listas [1, 2]
    res_qualify = execute_readonly_sql(
        """
        FROM notas
        SELECT id, nota
        QUALIFY RANK() OVER (ORDER BY nota DESC) = 1;
        """,
        db_path=seeded_duckdb,
        engine="duckdb",
    )
    assert res_qualify.rows[0][1] == 10 or res_qualify.rows[0][1] >= 9.5

    res_anti = execute_readonly_sql(
        "FROM alunos a ANTI JOIN alunos_disciplinas ad ON ad.aluno_id = a.id SELECT a.id ORDER BY a.id;",
        db_path=seeded_duckdb,
        engine="duckdb",
    )
    assert res_anti.rows == [[25], [50]]

    res_pivot = execute_readonly_sql(
        "PIVOT (FROM alunos_disciplinas SELECT status) ON status IN ('cursando', 'concluida', 'trancada') USING COUNT(*);",
        db_path=seeded_duckdb,
        engine="duckdb",
    )
    assert res_pivot.columns == ["cursando", "concluida", "trancada"]
    assert sum(res_pivot.rows[0]) == 108

    res_replace = execute_readonly_sql(
        "SELECT * EXCLUDE (email, data_contratacao) REPLACE (UPPER(nome) AS nome) FROM professores LIMIT 1;",
        db_path=seeded_duckdb,
        engine="duckdb",
    )
    assert "email" not in res_replace.columns
    assert res_replace.rows[0][1] == res_replace.rows[0][1].upper()

    res_summarize = execute_readonly_sql("SUMMARIZE alunos;", db_path=seeded_duckdb, engine="duckdb")
    assert res_summarize.row_count == 6

    res_list = execute_readonly_sql("SELECT [1, 2, 3] AS arr;", db_path=seeded_duckdb, engine="duckdb")
    assert res_list.rows == [[[1, 2, 3]]]


@pytest.mark.parametrize(
    "bad_duckdb_sql",
    [
        "",
        "DROP TABLE alunos;",
        "DELETE FROM alunos WHERE id = 1;",
        "INSERT INTO cursos VALUES (99, 'X', 'Y', 10);",
        "UPDATE alunos SET idade = 99;",
        "ATTACH ':memory:' AS x;",
        "COPY alunos TO 'out.csv';",
        "SET enable_external_access = true;",
        "PRAGMA version;",
        "CALL duckdb_tables();",
        "INSTALL httpfs;",
        "LOAD httpfs;",
        "SELECT * FROM read_text('README.md');",
        "SELECT * FROM read_csv('foo.csv');",
        "SELECT * FROM read_parquet('foo.parquet');",
        "SELECT * FROM glob('*');",
        "SELECT current_setting('threads');",
        "SELECT * FROM pragma_database_list;",
        "SELECT * FROM duckdb_logs();",
        "FROM alunos SELECT nome; DROP TABLE alunos;",
        "/* outer /* inner */ DELETE FROM alunos; */",
    ],
)
def test_duckdb_blocks_unsafe_sql_in_validator(bad_duckdb_sql: str) -> None:
    with pytest.raises(SQLValidationError):
        validate_readonly_sql(bad_duckdb_sql, engine="duckdb")


def test_duckdb_sandbox_blocks_external_access_and_mutations_directly(seeded_duckdb: Path) -> None:
    conn = connect_duckdb_readonly(seeded_duckdb)
    try:
        for unsafe_query in [
            "SELECT * FROM read_text('README.md')",
            "SELECT * FROM read_csv('nao_existe.csv')",
            "FROM 'README.md'",
            "ATTACH ':memory:' AS hack",
            "SET enable_external_access = true",
            "DROP TABLE alunos",
        ]:
            with pytest.raises(duckdb.Error):
                conn.execute(unsafe_query).fetchall()
    finally:
        conn.close()


def test_duckdb_timeout_limit_inf_and_explain(seeded_duckdb: Path) -> None:
    limited = execute_readonly_sql(
        "FROM notas SELECT id;",
        db_path=seeded_duckdb,
        max_rows=5,
        engine="duckdb",
    )
    assert limited.row_count == 5
    assert limited.truncated is True

    with pytest.raises(SQLValidationError):
        execute_readonly_sql("SELECT 1e999::DOUBLE;", db_path=seeded_duckdb, engine="duckdb")

    heavy_sql = """
    WITH RECURSIVE loop(x) AS (
        SELECT 1
        UNION ALL
        SELECT x + 1 FROM loop
    )
    SELECT COUNT(*) FROM loop;
    """
    with pytest.raises(TimeoutError):
        execute_readonly_sql(heavy_sql, db_path=seeded_duckdb, timeout_seconds=0.05, engine="duckdb")

    plan = explain_readonly_sql(
        "FROM alunos SELECT nome WHERE idade > 30;",
        db_path=seeded_duckdb,
        engine="duckdb",
    )
    assert plan.row_count >= 1
    assert any("Seq Scan" in str(cell) or "physical_plan" in str(cell) for row in plan.rows for cell in row)


@pytest.mark.parametrize(
    ("raw_error", "expected_snippet"),
    [
        ('Binder Error: Ambiguous reference to column name "id" (use: \'a.id\' or \'n.id\')', "apelido"),
        ('Binder Error: Referenced column "x" not found in FROM clause!', "esquema"),
        ("Catalog Error: Table with name turma does not exist!", "professores"),
        ("Binder Error: Combining QUALIFY with GROUP BY ALL is not supported yet", "GROUP BY"),
        ("Binder Error: WHERE clause cannot contain window functions!", "QUALIFY"),
        ("Binder Error: WHERE clause cannot contain aggregates!", "HAVING"),
        ('Binder Error: column "cidade" must appear in the GROUP BY clause', "GROUP BY ALL"),
        ("Catalog Error: Scalar Function with name foo does not exist!", "Guia SQL"),
        ("Binder Error: No function matches the given name and argument types 'strftime(VARCHAR, DATE)'", "YEAR"),
        ('Parser Error: syntax error at or near "alunos"', "sintaxe"),
        ("Binder Error: Cannot compare values of type DATE and type INTEGER_LITERAL", "DATE"),
        ("Permission Error: Cannot access file - file system operations are disabled by configuration", "somente leitura"),
    ],
)
def test_translate_duckdb_error_returns_friendly_hints(
    raw_error: str, expected_snippet: str
) -> None:
    hint = translate_sql_error(raw_error, engine="duckdb")
    assert hint is not None
    assert expected_snippet.lower() in hint.lower()
    assert translate_duckdb_error("erro desconhecido qualquer") is None
