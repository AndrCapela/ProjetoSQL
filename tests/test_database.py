"""Testes da criação, relacionamentos e metadados do banco SQLite."""

import sqlite3
from pathlib import Path

from app.database import create_and_seed_database, get_schema_metadata


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
