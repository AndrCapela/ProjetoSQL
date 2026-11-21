"""Testes da criação, relacionamentos e metadados dos bancos SQLite e DuckDB."""

import sqlite3
from pathlib import Path

import duckdb

from app.database import (
    connect_duckdb_readonly,
    create_and_seed_all_databases,
    create_and_seed_database,
    get_schema_metadata,
)
from app.sql_executor import _sanitize_cell


def test_seed_creates_expected_tables_and_counts(tmp_path: Path) -> None:
    db_path = tmp_path / "test_escola.db"
    create_and_seed_database(db_path=db_path, overwrite=True)

    metadata = get_schema_metadata(db_path)
    counts = {table["name"]: table["row_count"] for table in metadata}

    assert set(counts.keys()) == {
        "professores",
        "cursos",
        "disciplinas",
        "alunos",
        "alunos_disciplinas",
        "notas",
    }
    assert counts["professores"] == 10
    assert counts["cursos"] == 12
    assert counts["disciplinas"] == 20
    assert counts["alunos"] == 50
    assert counts["alunos_disciplinas"] >= 100
    assert counts["notas"] >= 150


def test_professor_disciplina_and_aluno_disciplina_relationships(tmp_path: Path) -> None:
    db_path = tmp_path / "test_rel.db"
    create_and_seed_database(db_path=db_path, overwrite=True)

    conn = sqlite3.connect(db_path)
    try:
        # Cada disciplina pertence a exatamente 1 professor válido, e existe professor com N disciplinas
        multi_prof = conn.execute(
            """
            SELECT professor_id, COUNT(*) AS qtd
            FROM disciplinas
            GROUP BY professor_id
            HAVING qtd > 1
            """
        ).fetchall()
        assert len(multi_prof) >= 1

        # Relação N:N: há alunos com múltiplas disciplinas e disciplinas com múltiplos alunos
        multi_disc_aluno = conn.execute(
            """
            SELECT aluno_id, COUNT(*) AS qtd
            FROM alunos_disciplinas
            GROUP BY aluno_id
            HAVING qtd > 1
            """
        ).fetchall()
        multi_aluno_disc = conn.execute(
            """
            SELECT disciplina_id, COUNT(*) AS qtd
            FROM alunos_disciplinas
            GROUP BY disciplina_id
            HAVING qtd > 1
            """
        ).fetchall()

        assert len(multi_disc_aluno) > 10
        assert len(multi_aluno_disc) >= 8

        indexes = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index' AND name LIKE 'idx_%';"
            ).fetchall()
        }
        assert {
            "idx_disciplinas_curso_id",
            "idx_disciplinas_professor_id",
            "idx_alunos_disciplinas_aluno_id",
            "idx_alunos_disciplinas_disciplina_id",
            "idx_notas_aluno_disciplina_id",
        }.issubset(indexes)
    finally:
        conn.close()


def test_duckdb_seed_parity_metadata_and_indexes(tmp_path: Path) -> None:
    sqlite_path, duckdb_path = create_and_seed_all_databases(
        sqlite_path=tmp_path / "parity.db",
        duckdb_path=tmp_path / "parity.duckdb",
        overwrite=True,
    )

    sqlite_meta = get_schema_metadata(sqlite_path, engine="sqlite")
    duckdb_meta = get_schema_metadata(duckdb_path, engine="duckdb")

    assert [t["name"] for t in duckdb_meta] == [t["name"] for t in sqlite_meta]
    assert {t["name"]: t["row_count"] for t in duckdb_meta} == {
        t["name"]: t["row_count"] for t in sqlite_meta
    }

    for sq_tbl, dk_tbl in zip(sqlite_meta, duckdb_meta):
        sq_cols = [
            (c["name"], c["nullable"] if not c["primary_key"] else False, c["primary_key"], c["foreign_key"])
            for c in sq_tbl["columns"]
        ]
        dk_cols = [(c["name"], c["nullable"], c["primary_key"], c["foreign_key"]) for c in dk_tbl["columns"]]
        assert dk_cols == sq_cols

    sq_conn = sqlite3.connect(sqlite_path)
    dk_conn = connect_duckdb_readonly(duckdb_path)
    try:
        for table_meta in sqlite_meta:
            name = table_meta["name"]
            sq_rows = [list(r) for r in sq_conn.execute(f'SELECT * FROM "{name}" ORDER BY id').fetchall()]
            dk_rows = [
                [_sanitize_cell(cell) for cell in r]
                for r in dk_conn.execute(f'SELECT * FROM "{name}" ORDER BY id').fetchall()
            ]
            assert dk_rows == sq_rows

        dk_indexes = {
            row[0]
            for row in dk_conn.execute(
                "SELECT index_name FROM duckdb_indexes() WHERE schema_name = 'main';"
            ).fetchall()
        }
        assert {
            "idx_disciplinas_curso_id",
            "idx_disciplinas_professor_id",
            "idx_alunos_disciplinas_aluno_id",
            "idx_alunos_disciplinas_disciplina_id",
            "idx_notas_aluno_disciplina_id",
        }.issubset(dk_indexes)

        temp_dir_setting = dk_conn.execute("SELECT current_setting('temp_directory')").fetchone()[0]
        assert str(duckdb_path.parent) not in str(temp_dir_setting)
    finally:
        sq_conn.close()
        dk_conn.close()
