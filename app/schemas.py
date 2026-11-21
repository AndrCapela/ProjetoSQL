"""Modelos Pydantic de entrada e saída da API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

DifficultyLevel = Literal["facil", "medio", "dificil"]
DatabaseEngine = Literal["sqlite", "duckdb"]


class ColumnSchema(BaseModel):
    """Metadados de uma coluna no banco de dados."""

    name: str
    type: str
    nullable: bool
    primary_key: bool
    foreign_key: str | None = None


class TableSchema(BaseModel):
    """Metadados de uma tabela no banco de dados."""

    name: str
    row_count: int
    columns: list[ColumnSchema]


class ChallengeSummary(BaseModel):
    """Representação pública de um desafio SQL."""

    id: str
    nivel: DifficultyLevel
    titulo: str
    enunciado: str
    dica: str
    ordem_importa: bool
    topicos: list[str]


class QueryPayload(BaseModel):
    """Payload de execução de consulta SQL."""

    sql: str = Field(..., min_length=1, max_length=10_000)
    challenge_id: str | None = None
    engine: DatabaseEngine = "sqlite"


class TableResult(BaseModel):
    """Resultado tabular de uma consulta SQL."""

    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    execution_ms: float
    truncated: bool = False


class ExpectedAnswer(BaseModel):
    """Gabarito com a consulta SQL oficial e seu resultado tabular."""

    sql: str
    result: TableResult


class ExecuteQueryResponse(BaseModel):
    """Resposta completa da execução no modo desafio ou modo livre."""

    mode: Literal["challenge", "free"]
    engine: DatabaseEngine = "sqlite"
    challenge_id: str | None = None
    user_result: TableResult | None = None
    user_error: str | None = None
    user_error_hint: str | None = None
    expected: ExpectedAnswer | None = None
    is_correct: bool | None = None
    feedback: str | None = None
    user_row_status: list[Literal["match", "extra", "order"]] | None = None
    expected_row_status: list[Literal["match", "missing", "order"]] | None = None


class ChatMessage(BaseModel):
    """Mensagem do histórico de conversa com o agente tutor."""

    role: Literal["user", "model"]
    text: str = Field(..., min_length=1, max_length=4_000)


class ChatPayload(BaseModel):
    """Payload de dúvida enviada pelo usuário ao agente tutor SQL."""

    message: str = Field(..., min_length=1, max_length=2_000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=12)
    sql: str | None = Field(default=None, max_length=10_000)
    challenge_id: str | None = None
    engine: DatabaseEngine = "sqlite"
    last_error: str | None = Field(default=None, max_length=2_000)
    last_feedback: str | None = Field(default=None, max_length=1_000)
    last_result_summary: str | None = Field(default=None, max_length=2_000)


class ChatResponse(BaseModel):
    """Resposta do agente tutor SQL."""

    reply: str
    model: str
    remaining_daily: int | None = None
