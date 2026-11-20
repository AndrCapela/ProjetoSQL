"""Testes de integração dos endpoints FastAPI."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.database import create_and_seed_database
from app.main import create_app


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    db_path = create_and_seed_database(tmp_path / "api_escola.db", overwrite=True)
    app = create_app(db_path=db_path)
    with TestClient(app) as test_client:
        yield test_client


def test_health_and_frontend_served(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}
    index_res = client.get("/")
    assert index_res.status_code == 200
    assert "SQL Arena" in index_res.text


def test_schema_and_browse_table_endpoints(client: TestClient) -> None:
    schema_res = client.get("/api/schema")
    assert schema_res.status_code == 200
    table_names = [t["name"] for t in schema_res.json()]
    assert "disciplinas" in table_names
    assert "alunos_disciplinas" in table_names

    browse_res = client.get("/api/tables/disciplinas?page=1&page_size=5&search=BD")
    assert browse_res.status_code == 200
    body = browse_res.json()
    assert body["table"] == "disciplinas"
    assert body["total_rows"] == 3
    assert len(body["rows"]) == 3

    missing = client.get("/api/tables/tabela_inexistente")
    assert missing.status_code == 404


def test_execute_challenge_correct_wrong_and_error_always_return_expected(client: TestClient) -> None:
    # 1. Resposta correta escrita com alias diferente e ordenação extra
    ok_res = client.post(
        "/api/execute",
        json={
            "challenge_id": "facil-1",
            "sql": "SELECT nome AS aluno, idade, cidade FROM alunos WHERE idade >= 31 ORDER BY nome;",
        },
    )
    assert ok_res.status_code == 200
    ok_data = ok_res.json()
    assert ok_data["is_correct"] is True
    assert ok_data["user_result"]["row_count"] > 0
    assert ok_data["expected"]["sql"]
    assert ok_data["expected"]["result"]["row_count"] == ok_data["user_result"]["row_count"]

    # 2. Resposta incorreta ainda exibe as duas tabelas (usuário + gabarito)
    wrong_res = client.post(
        "/api/execute",
        json={
            "challenge_id": "facil-1",
            "sql": "SELECT nome, idade, cidade FROM alunos WHERE idade > 99;",
        },
    )
    assert wrong_res.status_code == 200
    wrong_data = wrong_res.json()
    assert wrong_data["is_correct"] is False
    assert wrong_data["user_result"]["row_count"] == 0
    assert wrong_data["expected"]["result"]["row_count"] > 0

    # 3. Erro SQL ou bloqueio de escrita ainda exibe o gabarito esperado
    err_res = client.post(
        "/api/execute",
        json={
            "challenge_id": "facil-1",
            "sql": "DROP TABLE alunos;",
        },
    )
    assert err_res.status_code == 200
    err_data = err_res.json()
    assert err_data["is_correct"] is False
    assert err_data["user_error"] is not None
    assert err_data["expected"]["result"]["row_count"] > 0


def test_execute_free_mode(client: TestClient) -> None:
    res = client.post(
        "/api/execute",
        json={"sql": "SELECT COUNT(*) AS total_disciplinas FROM disciplinas;"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["mode"] == "free"
    assert data["expected"] is None
    assert data["user_result"]["rows"] == [[20]]


def test_explain_endpoint_valid_and_blocked(client: TestClient) -> None:
    ok_res = client.post(
        "/api/explain",
        json={"sql": "SELECT nome FROM alunos WHERE idade > 30;"},
    )
    assert ok_res.status_code == 200
    ok_data = ok_res.json()
    assert ok_data["error"] is None
    assert ok_data["result"]["row_count"] >= 1

    bad_res = client.post(
        "/api/explain",
        json={"sql": "DELETE FROM alunos;"},
    )
    assert bad_res.status_code == 200
    assert bad_res.json()["error"] is not None


def test_execute_returns_error_hint_and_row_diff_statuses(client: TestClient) -> None:
    col_err = client.post(
        "/api/execute",
        json={
            "challenge_id": "facil-1",
            "sql": "SELECT coluna_inexistente FROM alunos;",
        },
    )
    assert col_err.status_code == 200
    col_data = col_err.json()
    assert col_data["user_error"] is not None
    assert col_data["user_error_hint"] is not None
    assert "esquema" in col_data["user_error_hint"].lower()

    partial = client.post(
        "/api/execute",
        json={
            "challenge_id": "facil-1",
            "sql": "SELECT nome, idade, cidade FROM alunos WHERE idade >= 30;",
        },
    )
    assert partial.status_code == 200
    partial_data = partial.json()
    assert partial_data["is_correct"] is False
    assert "extra" in partial_data["user_row_status"]
    assert all(s == "match" for s in partial_data["expected_row_status"])


def test_security_headers_and_rate_limiting(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = create_and_seed_database(tmp_path / "sec_escola.db", overwrite=True)
    monkeypatch.setenv("APP_ENV", "production")
    sec_app = create_app(db_path=db_path, rate_limit_per_minute=2)

    with TestClient(sec_app) as sec_client:
        health = sec_client.get("/api/health")
        assert health.status_code == 200
        assert health.headers["x-content-type-options"] == "nosniff"
        assert health.headers["x-frame-options"] == "DENY"
        assert "default-src 'self'" in health.headers["content-security-policy"]
        assert sec_client.get("/docs").status_code == 404

        r1 = sec_client.post("/api/execute", json={"sql": "SELECT 1;"})
        r2 = sec_client.post("/api/execute", json={"sql": "SELECT 1;"})
        r3 = sec_client.post("/api/execute", json={"sql": "SELECT 1;"})
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 429

        # Tentativa de spoofing no primeiro item de X-Forwarded-For não deve burlar o limite
        spoof = sec_client.post(
            "/api/execute",
            json={"sql": "SELECT 1;"},
            headers={"X-Forwarded-For": "8.8.8.8, 203.0.113.10"},
        )
        spoof2 = sec_client.post(
            "/api/execute",
            json={"sql": "SELECT 1;"},
            headers={"X-Forwarded-For": "1.1.1.1, 203.0.113.10"},
        )
        spoof3 = sec_client.post(
            "/api/execute",
            json={"sql": "SELECT 1;"},
            headers={"X-Forwarded-For": "9.9.9.9, 203.0.113.10"},
        )
        assert spoof.status_code == 200
        assert spoof2.status_code == 200
        assert spoof3.status_code == 429


def test_execute_handles_non_json_sqlite_values_and_like_escaping(client: TestClient) -> None:
    inf_res = client.post("/api/execute", json={"sql": "SELECT 1e999;"})
    assert inf_res.status_code == 200
    assert inf_res.json()["user_error"] is not None

    blob_res = client.post("/api/execute", json={"sql": "SELECT X'ff00';"})
    assert blob_res.status_code == 200
    assert blob_res.json()["user_result"]["rows"] == [["X'FF00'"]]

    wildcard_res = client.get("/api/tables/alunos?search=%25")
    assert wildcard_res.status_code == 200
    assert wildcard_res.json()["total_rows"] == 0
