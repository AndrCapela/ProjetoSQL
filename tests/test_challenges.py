"""Valida todo o catálogo de desafios contra o banco populado."""

from pathlib import Path

import pytest

from app.challenges import CHALLENGES, list_challenges
from app.comparator import compare_results
from app.database import create_and_seed_database
from app.sql_executor import execute_readonly_sql


@pytest.fixture(scope="module")
def db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    db_file = tmp_path_factory.mktemp("challenges") / "escola.db"
    return create_and_seed_database(db_file, overwrite=True)


def test_challenge_distribution_and_unique_ids() -> None:
    ids = [c.id for c in CHALLENGES]
    assert len(ids) == len(set(ids))
    assert len(list_challenges("facil")) == 10
    assert len(list_challenges("medio")) == 10
    assert len(list_challenges("dificil")) == 10


@pytest.mark.parametrize("challenge", CHALLENGES, ids=lambda c: c.id)
def test_every_challenge_solution_executes_and_returns_data(challenge, db_path: Path) -> None:
    result = execute_readonly_sql(challenge.solucao_sql, db_path=db_path)
    assert len(result.columns) >= 1
    assert result.row_count >= 1
    assert compare_results(result, result, order_matters=challenge.ordem_importa).is_correct is True


def test_alternative_queries_for_same_challenge_pass(db_path: Path) -> None:
    # Desafio dificil-1: NOT EXISTS deve equivaler ao LEFT JOIN ... IS NULL
    expected = execute_readonly_sql(
        next(c.solucao_sql for c in CHALLENGES if c.id == "dificil-1"),
        db_path=db_path,
    )
    alt_not_exists = execute_readonly_sql(
        """
        SELECT a.id, a.nome, a.email
        FROM alunos a
        WHERE NOT EXISTS (
            SELECT 1 FROM alunos_disciplinas ad WHERE ad.aluno_id = a.id
        );
        """,
        db_path=db_path,
    )
    assert compare_results(alt_not_exists, expected, order_matters=False).is_correct is True
