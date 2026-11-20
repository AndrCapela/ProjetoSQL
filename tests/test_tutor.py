"""Testes do agente Tutor SQL (Google Gemini) e endpoints de chat."""

from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.challenges import get_challenge
from app.database import create_and_seed_database, get_schema_metadata
from app.main import create_app
from app.schemas import ChatPayload
from app.tutor import build_schema_context, build_user_turn_with_context


class _FakeHttpxResponse:
    def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


def test_build_schema_and_user_context(tmp_path: Path) -> None:
    db_path = create_and_seed_database(tmp_path / "tutor.db", overwrite=True)
    schema = get_schema_metadata(db_path)
    schema_text = build_schema_context(schema)
    assert "alunos (" in schema_text
    assert "FK->alunos.id" in schema_text

    payload = ChatPayload(
        message="Por que deu erro?",
        sql="SELECT YEAR(data_matricula) FROM alunos;",
        challenge_id="dificil-7",
        last_error="no such function: YEAR",
    )
    ctx = build_user_turn_with_context(payload, get_challenge("dificil-7"))
    assert "dificil-7" in ctx
    assert "SELECT YEAR(data_matricula) FROM alunos;" in ctx
    assert "no such function: YEAR" in ctx
    assert "Por que deu erro?" in ctx


def test_chat_endpoint_returns_503_when_api_key_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    db_path = create_and_seed_database(tmp_path / "chat_nokey.db", overwrite=True)
    app = create_app(db_path=db_path)

    with TestClient(app) as client:
        status = client.get("/api/chat/status")
        assert status.status_code == 200
        assert status.json()["enabled"] is False

        res = client.post("/api/chat", json={"message": "Por que minha query falhou?"})
        assert res.status_code == 503
        assert "GEMINI_API_KEY" in res.json()["detail"]


def test_chat_endpoint_calls_gemini_with_context_and_rate_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-fake-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")

    captured: dict[str, Any] = {}

    def fake_post(url: str, *, headers: dict[str, str], json: dict[str, Any], timeout: float):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeHttpxResponse(
            200,
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": "No SQLite, use `strftime('%Y', data_matricula)` em vez de `YEAR()`."}
                            ]
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    db_path = create_and_seed_database(tmp_path / "chat_ok.db", overwrite=True)
    app = create_app(db_path=db_path, chat_rate_limit_per_minute=2)

    with TestClient(app) as client:
        status = client.get("/api/chat/status")
        assert status.status_code == 200
        assert status.json()["enabled"] is True
        assert status.json()["model"] == "gemini-2.5-flash"
        assert "gemini-3.5-flash" in status.json()["fallback_models"]

        r1 = client.post(
            "/api/chat",
            json={
                "message": "Por que deu erro?",
                "sql": "SELECT YEAR(data_matricula) FROM alunos;",
                "challenge_id": "dificil-7",
                "last_error": "no such function: YEAR",
            },
        )
        assert r1.status_code == 200
        assert "strftime" in r1.json()["reply"]
        assert r1.json()["model"] == "gemini-2.5-flash"
        assert captured["headers"]["x-goog-api-key"] == "test-fake-key"
        assert "gemini-2.5-flash:generateContent" in captured["url"]
        sent_user_text = captured["json"]["contents"][-1]["parts"][0]["text"]
        assert "SELECT YEAR(data_matricula) FROM alunos;" in sent_user_text
        assert "no such function: YEAR" in sent_user_text
        system_text = captured["json"]["system_instruction"]["parts"][0]["text"]
        assert "EXCLUSIVAMENTE" in system_text
        assert "recuse educadamente" in system_text

        r2 = client.post("/api/chat", json={"message": "Entendi, obrigado!"})
        assert r2.status_code == 200

        r3 = client.post("/api/chat", json={"message": "Mais uma dúvida"})
        assert r3.status_code == 429


def test_chat_endpoint_falls_back_when_primary_model_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-fake-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "gemini-3.5-flash,gemini-2.5-flash")

    called_urls: list[str] = []

    def fake_post(url: str, *, headers: dict[str, str], json: dict[str, Any], timeout: float):
        called_urls.append(url)
        if "gemini-3.5-flash-lite" in url:
            return _FakeHttpxResponse(503, {"error": {"message": "Model overloaded"}})
        return _FakeHttpxResponse(
            200,
            {"candidates": [{"content": {"parts": [{"text": "Resposta via fallback."}]}}]},
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    db_path = create_and_seed_database(tmp_path / "chat_fallback.db", overwrite=True)
    app = create_app(db_path=db_path)

    with TestClient(app) as client:
        res = client.post("/api/chat", json={"message": "Minha query falhou"})
        assert res.status_code == 200
        assert res.json()["reply"] == "Resposta via fallback."
        assert res.json()["model"] == "gemini-3.5-flash"
        assert len(called_urls) == 2

    # Em erro de autenticação (401), não deve tentar os modelos de fallback
    auth_calls: list[str] = []

    def fake_auth_fail(url: str, *, headers: dict[str, str], json: dict[str, Any], timeout: float):
        auth_calls.append(url)
        return _FakeHttpxResponse(401, {"error": {"message": "API key invalid"}})

    monkeypatch.setattr(httpx, "post", fake_auth_fail)
    with TestClient(app) as client:
        res_auth = client.post("/api/chat", json={"message": "Teste"})
        assert res_auth.status_code == 502
        assert len(auth_calls) == 1


def test_chat_thinking_config_and_daily_limit_controls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-fake-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "gemini-2.5-flash")
    monkeypatch.setenv("GEMINI_THINKING_LEVEL", "minimal")
    monkeypatch.setenv("GEMINI_MAX_OUTPUT_TOKENS", "350")

    sent_configs: list[tuple[str, dict[str, Any]]] = []

    def fake_post(url: str, *, headers: dict[str, str], json: dict[str, Any], timeout: float):
        sent_configs.append((url, json["generationConfig"]))
        if "gemini-3.5-flash-lite" in url and len(sent_configs) == 1:
            return _FakeHttpxResponse(503, {"error": {"message": "Temporarily unavailable"}})
        return _FakeHttpxResponse(
            200,
            {"candidates": [{"content": {"parts": [{"text": "Dica curta."}]}}]},
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    db_path = create_and_seed_database(tmp_path / "chat_limits.db", overwrite=True)
    app = create_app(
        db_path=db_path,
        chat_rate_limit_per_minute=10,
        chat_daily_limit_per_user=2,
    )

    with TestClient(app) as client:
        status = client.get("/api/chat/status").json()
        assert status["daily_limit"] == 2
        assert status["max_output_tokens"] == 350
        assert status["thinking_level"] == "minimal"

        # 1a pergunta: 3.5-flash-lite envia thinkingLevel="minimal" e falha 503; 2.5-flash recebe thinkingBudget=0
        r1 = client.post("/api/chat", json={"message": "Pergunta 1"})
        assert r1.status_code == 200
        assert r1.json()["model"] == "gemini-2.5-flash"
        assert r1.json()["remaining_daily"] == 1
        assert sent_configs[0][1]["maxOutputTokens"] == 350
        assert sent_configs[0][1]["thinkingConfig"] == {"thinkingLevel": "minimal"}
        assert sent_configs[1][1]["thinkingConfig"] == {"thinkingBudget": 0}

        # 2a pergunta: consome o último slot diário
        r2 = client.post("/api/chat", json={"message": "Pergunta 2"})
        assert r2.status_code == 200
        assert r2.json()["remaining_daily"] == 0

        # 3a pergunta no mesmo dia: bloqueada com HTTP 429
        r3 = client.post("/api/chat", json={"message": "Pergunta 3"})
        assert r3.status_code == 429
        assert "diário" in r3.json()["detail"].lower()
