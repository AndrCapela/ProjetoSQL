"""Aplicação FastAPI para a plataforma de treinamento SQL."""

from __future__ import annotations

import os
import sqlite3
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.challenges import Challenge, get_challenge, list_challenges
from app.comparator import compare_results
from app.database import DEFAULT_DB_PATH, ensure_database, get_schema_metadata
from app.schemas import (
    ChallengeSummary,
    DifficultyLevel,
    ExecuteQueryResponse,
    ExpectedAnswer,
    QueryPayload,
    TableResult,
    TableSchema,
)
from app.sql_executor import (
    SQLExecutionResult,
    SQLValidationError,
    execute_readonly_sql,
    explain_readonly_sql,
    translate_sqlite_error,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    ),
}


class SlidingWindowRateLimiter:
    """Limitador de requisições em janela deslizante por IP (em memória)."""

    def __init__(self, max_requests: int, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str) -> None:
        if self.max_requests <= 0:
            return
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            bucket = self._hits[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.max_requests:
                raise HTTPException(
                    status_code=429,
                    detail=(
                        f"Limite de {self.max_requests} consultas por minuto atingido. "
                        "Aguarde alguns segundos e tente novamente."
                    ),
                )
            bucket.append(now)


def _extract_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


def _to_table_result(res: SQLExecutionResult) -> TableResult:
    return TableResult(
        columns=res.columns,
        rows=res.rows,
        row_count=res.row_count,
        execution_ms=res.execution_ms,
        truncated=res.truncated,
    )


def _to_challenge_summary(ch: Challenge) -> ChallengeSummary:
    return ChallengeSummary(
        id=ch.id,
        nivel=ch.nivel,
        titulo=ch.titulo,
        enunciado=ch.enunciado,
        dica=ch.dica,
        ordem_importa=ch.ordem_importa,
        topicos=list(ch.topicos),
    )


def create_app(
    db_path: Path = DEFAULT_DB_PATH,
    rate_limit_per_minute: int | None = None,
) -> FastAPI:
    """Factory da aplicação FastAPI com caminho de banco e rate limit configuráveis."""
    app_env = os.getenv("APP_ENV", "development").strip().lower()
    is_prod = app_env == "production"

    limit = (
        rate_limit_per_minute
        if rate_limit_per_minute is not None
        else int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    )
    limiter = SlidingWindowRateLimiter(max_requests=limit, window_seconds=60)

    def enforce_rate_limit(request: Request) -> None:
        limiter.check(_extract_client_ip(request))

    @asynccontextmanager
    async def lifespan(app_instance: FastAPI):
        ensure_database(app_instance.state.db_path)
        yield

    application = FastAPI(
        title="SQL Arena — Treinamento Interativo de SQL",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None if is_prod else "/docs",
        redoc_url=None if is_prod else "/redoc",
        openapi_url=None if is_prod else "/openapi.json",
    )
    application.state.db_path = Path(db_path)

    allowed_hosts_env = os.getenv("ALLOWED_HOSTS", "*").strip()
    if allowed_hosts_env and allowed_hosts_env != "*":
        hosts = [h.strip() for h in allowed_hosts_env.split(",") if h.strip()]
        if hosts:
            application.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)

    @application.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response

    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @application.get("/", include_in_schema=False)
    async def serve_index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @application.get("/api/health")
    async def health_check() -> dict[str, str]:
        ensure_database(application.state.db_path)
        return {"status": "ok"}

    @application.get("/api/schema", response_model=list[TableSchema])
    async def get_schema() -> list[TableSchema]:
        metadata = get_schema_metadata(application.state.db_path)
        return [TableSchema(**table) for table in metadata]

    @application.get("/api/tables/{table_name}")
    async def browse_table(
        table_name: str,
        page: int = Query(1, ge=1),
        page_size: int = Query(15, ge=1, le=100),
        search: str = Query("", max_length=100),
        sort_by: str | None = Query(None),
        sort_dir: Literal["asc", "desc"] = Query("asc"),
    ) -> dict[str, Any]:
        """Retorna dados paginados e filtráveis de uma tabela válida do esquema."""
        schema = get_schema_metadata(application.state.db_path)
        table_map = {t["name"]: t for t in schema}
        if table_name not in table_map:
            raise HTTPException(status_code=404, detail="Tabela não encontrada.")

        valid_columns = [c["name"] for c in table_map[table_name]["columns"]]
        order_col = sort_by if sort_by in valid_columns else valid_columns[0]
        order_direction = "DESC" if sort_dir == "desc" else "ASC"

        where_clause = ""
        params: list[Any] = []
        term = search.strip()
        if term:
            like_parts = [f'CAST("{col}" AS TEXT) LIKE ?' for col in valid_columns]
            where_clause = "WHERE " + " OR ".join(like_parts)
            params.extend([f"%{term}%"] * len(valid_columns))

        db_file = Path(application.state.db_path).resolve()
        conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
        try:
            conn.execute("PRAGMA query_only = ON;")
            total_rows = conn.execute(
                f'SELECT COUNT(*) FROM "{table_name}" {where_clause}',
                params,
            ).fetchone()[0]

            offset = (page - 1) * page_size
            cursor = conn.execute(
                f'SELECT * FROM "{table_name}" {where_clause} '
                f'ORDER BY "{order_col}" {order_direction} LIMIT ? OFFSET ?',
                [*params, page_size, offset],
            )
            rows = [list(r) for r in cursor.fetchall()]
        finally:
            conn.close()

        return {
            "table": table_name,
            "columns": valid_columns,
            "rows": rows,
            "page": page,
            "page_size": page_size,
            "total_rows": total_rows,
            "total_pages": max(1, (total_rows + page_size - 1) // page_size),
        }

    @application.get("/api/challenges", response_model=list[ChallengeSummary])
    async def get_challenges(
        nivel: DifficultyLevel | None = Query(None),
    ) -> list[ChallengeSummary]:
        return [_to_challenge_summary(ch) for ch in list_challenges(nivel)]

    @application.post(
        "/api/execute",
        response_model=ExecuteQueryResponse,
        dependencies=[Depends(enforce_rate_limit)],
    )
    async def execute_query(payload: QueryPayload) -> ExecuteQueryResponse:
        current_db = application.state.db_path

        if payload.challenge_id is None:
            try:
                user_res = execute_readonly_sql(payload.sql, db_path=current_db)
                return ExecuteQueryResponse(
                    mode="free",
                    user_result=_to_table_result(user_res),
                )
            except (SQLValidationError, sqlite3.Error, TimeoutError) as exc:
                return ExecuteQueryResponse(
                    mode="free",
                    user_error=str(exc),
                    user_error_hint=translate_sqlite_error(str(exc)),
                )

        challenge = get_challenge(payload.challenge_id)
        if challenge is None:
            raise HTTPException(status_code=404, detail="Desafio não encontrado.")

        expected_res = execute_readonly_sql(challenge.solucao_sql, db_path=current_db)
        expected_answer = ExpectedAnswer(
            sql=challenge.solucao_sql,
            result=_to_table_result(expected_res),
        )

        try:
            user_res = execute_readonly_sql(payload.sql, db_path=current_db)
        except (SQLValidationError, sqlite3.Error, TimeoutError) as exc:
            return ExecuteQueryResponse(
                mode="challenge",
                challenge_id=challenge.id,
                user_error=str(exc),
                user_error_hint=translate_sqlite_error(str(exc)),
                expected=expected_answer,
                is_correct=False,
                feedback=f"Erro na sua consulta: {exc}",
            )

        comparison = compare_results(
            user_res,
            expected_res,
            order_matters=challenge.ordem_importa,
        )
        return ExecuteQueryResponse(
            mode="challenge",
            challenge_id=challenge.id,
            user_result=_to_table_result(user_res),
            expected=expected_answer,
            is_correct=comparison.is_correct,
            feedback=comparison.feedback,
            user_row_status=comparison.user_row_status,
            expected_row_status=comparison.expected_row_status,
        )

    @application.post(
        "/api/explain",
        dependencies=[Depends(enforce_rate_limit)],
    )
    async def explain_query(payload: QueryPayload) -> dict[str, Any]:
        """Retorna o plano de execução SQLite (EXPLAIN QUERY PLAN) para fins didáticos."""
        try:
            res = explain_readonly_sql(payload.sql, db_path=application.state.db_path)
            return {"result": _to_table_result(res), "error": None}
        except (SQLValidationError, sqlite3.Error, TimeoutError) as exc:
            return {"result": None, "error": str(exc)}

    return application


app = create_app()
