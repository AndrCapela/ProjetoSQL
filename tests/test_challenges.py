"""Valida todo o catálogo de desafios nos bancos SQLite e DuckDB (Friendly SQL)."""

from pathlib import Path

import pytest

from app.challenges import CHALLENGES, get_challenge, list_challenges
from app.comparator import compare_results
from app.database import create_and_seed_database, create_and_seed_duckdb
from app.sql_executor import execute_readonly_sql


@pytest.fixture(scope="module")
def db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    db_file = tmp_path_factory.mktemp("challenges") / "escola.db"
    return create_and_seed_database(db_file, overwrite=True)


@pytest.fixture(scope="module")
def duckdb_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    db_file = tmp_path_factory.mktemp("challenges_duckdb") / "escola.duckdb"
    return create_and_seed_duckdb(db_file, overwrite=True)


def test_challenge_distribution_and_unique_ids() -> None:
    ids = [c.id for c in CHALLENGES]
    assert len(ids) == len(set(ids))
    assert len(list_challenges("facil")) == 10
    assert len(list_challenges("medio")) == 15
    assert len(list_challenges("dificil")) == 15
    assert all(c.solucao_duckdb.strip() for c in CHALLENGES)
    assert all(c.get_hint("duckdb").strip() for c in CHALLENGES)


@pytest.mark.parametrize("challenge", CHALLENGES, ids=lambda c: c.id)
def test_every_challenge_solution_executes_and_returns_data(challenge, db_path: Path) -> None:
    result = execute_readonly_sql(challenge.solucao_sql, db_path=db_path)
    assert len(result.columns) >= 1
    assert result.row_count >= 1
    assert compare_results(result, result, order_matters=challenge.ordem_importa).is_correct is True


@pytest.mark.parametrize("challenge", CHALLENGES, ids=lambda c: c.id)
def test_every_challenge_duckdb_matches_sqlite_exactly(
    challenge,
    db_path: Path,
    duckdb_path: Path,
) -> None:
    sqlite_res = execute_readonly_sql(
        challenge.get_solution("sqlite"),
        db_path=db_path,
        engine="sqlite",
    )
    duckdb_res = execute_readonly_sql(
        challenge.get_solution("duckdb"),
        db_path=duckdb_path,
        engine="duckdb",
    )
    assert len(duckdb_res.columns) >= 1
    assert duckdb_res.row_count >= 1
    cmp = compare_results(duckdb_res, sqlite_res, order_matters=challenge.ordem_importa)
    assert cmp.is_correct is True, f"{challenge.id}: {cmp.feedback}"


def test_standard_sql_also_accepted_on_duckdb(duckdb_path: Path) -> None:
    for challenge in CHALLENGES:
        if challenge.id == "dificil-7":
            continue
        ansi_res = execute_readonly_sql(
            challenge.solucao_sql,
            db_path=duckdb_path,
            engine="duckdb",
        )
        friendly_res = execute_readonly_sql(
            challenge.get_solution("duckdb"),
            db_path=duckdb_path,
            engine="duckdb",
        )
        cmp = compare_results(ansi_res, friendly_res, order_matters=challenge.ordem_importa)
        assert cmp.is_correct is True, f"ANSI vs Friendly on DuckDB failed for {challenge.id}: {cmp.feedback}"

    # No DuckDB, strftime(data, '%Y') (sintaxe alternativa ao YEAR()) também deve ser aceita
    ch7 = get_challenge("dificil-7")
    assert ch7 is not None
    alt_ch7 = execute_readonly_sql(
        """
        SELECT nome, cidade, data_matricula
        FROM alunos
        WHERE strftime(data_matricula, '%Y') = '2025'
        ORDER BY data_matricula ASC, nome ASC;
        """,
        db_path=duckdb_path,
        engine="duckdb",
    )
    expected_ch7 = execute_readonly_sql(
        ch7.get_solution("duckdb"),
        db_path=duckdb_path,
        engine="duckdb",
    )
    assert compare_results(alt_ch7, expected_ch7, order_matters=True).is_correct is True


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

    # Desafio dificil-11: NOT EXISTS deve equivaler ao HAVING COUNT = SUM(CASE WHEN ...)
    expected_11 = execute_readonly_sql(
        next(c.solucao_sql for c in CHALLENGES if c.id == "dificil-11"),
        db_path=db_path,
    )
    alt_11 = execute_readonly_sql(
        """
        SELECT a.id, a.nome, COUNT(ad.id) AS total_concluidas
        FROM alunos a
        INNER JOIN alunos_disciplinas ad ON ad.aluno_id = a.id
        WHERE NOT EXISTS (
            SELECT 1
            FROM alunos_disciplinas ad2
            WHERE ad2.aluno_id = a.id AND ad2.status != 'concluida'
        )
        GROUP BY a.id, a.nome
        ORDER BY total_concluidas DESC, a.nome ASC;
        """,
        db_path=db_path,
    )
    assert compare_results(alt_11, expected_11, order_matters=True).is_correct is True
