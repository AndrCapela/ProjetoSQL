"""Aplicação FastAPI para a plataforma de treinamento SQL."""

from __future__ import annotations

import os
import sqlite3
import sys
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock
from typing import Any, Literal

import duckdb
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.challenges import Challenge, get_challenge, list_challenges
from app.comparator import compare_results
from app.database import (
    DEFAULT_DB_PATH,
    DEFAULT_DUCKDB_PATH,
    connect_duckdb_readonly,
    ensure_database,
    get_schema_metadata,
)
from app.schemas import (
    ChallengeSummary,
    ChatPayload,
    ChatResponse,
    DatabaseEngine,
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
    _sanitize_cell,
    execute_readonly_sql,
    explain_readonly_sql,
    translate_sql_error,
)
from app.tutor import (
    TutorConfigError,
    TutorUpstreamError,
    ask_gemini_tutor,
    get_tutor_config,
    get_tutor_limits,
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
    """Limitador de requisições em janela deslizante por IP (em memória, com limpeza)."""

    def __init__(
        self,
        max_requests: int,
        window_seconds: int = 60,
        detail_message: str | None = None,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.detail_message = detail_message
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()
        self._checks = 0

    def _prune_stale_buckets(self, cutoff: float) -> None:
        stale_keys = [
            ip for ip, dq in self._hits.items()
            if not dq or dq[-1] <= cutoff
        ]
        for ip in stale_keys:
            del self._hits[ip]

    def remaining(self, key: str) -> int | None:
        if self.max_requests <= 0:
            return None
        cutoff = time.monotonic() - self.window_seconds
        with self._lock:
            bucket = self._hits.get(key)
            if not bucket:
                return self.max_requests
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            return max(0, self.max_requests - len(bucket))

    def check(self, key: str) -> None:
        if self.max_requests <= 0:
            return
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            self._checks += 1
            if self._checks % 100 == 0 or len(self._hits) > 1000:
                self._prune_stale_buckets(cutoff)

            bucket = self._hits[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.max_requests:
                raise HTTPException(
                    status_code=429,
                    detail=self.detail_message
                    or (
                        f"Limite de {self.max_requests} requisições por minuto atingido. "
                        "Aguarde alguns segundos e tente novamente."
                    ),
                )
            bucket.append(now)


def _extract_client_ip(request: Request) -> str:
    """Obtém o IP real do cliente evitando spoofing no primeiro item de X-Forwarded-For."""
    real_ip = request.headers.get("x-real-ip")
    if real_ip and real_ip.strip():
        return real_ip.strip()
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if parts:
            return parts[-1]
    return request.client.host if request.client else "unknown"


def _to_table_result(res: SQLExecutionResult) -> TableResult:
    return TableResult(
        columns=res.columns,
        rows=res.rows,
        row_count=res.row_count,
        execution_ms=res.execution_ms,
        truncated=res.truncated,
    )


def _to_challenge_summary(
    ch: Challenge,
    engine: DatabaseEngine = "sqlite",
) -> ChallengeSummary:
    return ChallengeSummary(
        id=ch.id,
        nivel=ch.nivel,
        titulo=ch.get_title(engine),
        enunciado=ch.get_description(engine),
        dica=ch.get_hint(engine),
        ordem_importa=ch.ordem_importa,
        topicos=list(ch.get_topics(engine)),
    )


def create_app(
    db_path: Path = DEFAULT_DB_PATH,
    duckdb_path: Path | None = None,
    rate_limit_per_minute: int | None = None,
    chat_rate_limit_per_minute: int | None = None,
    chat_daily_limit_per_user: int | None = None,
) -> FastAPI:
    """Factory da aplicação FastAPI com caminhos de banco e rate limit configuráveis."""
    app_env = os.getenv("APP_ENV", "development").strip().lower()
    is_prod = app_env == "production"

    sqlite_db_path = Path(db_path)
    if duckdb_path is not None:
        resolved_duckdb_path = Path(duckdb_path)
    elif sqlite_db_path == DEFAULT_DB_PATH:
        resolved_duckdb_path = DEFAULT_DUCKDB_PATH
    else:
        resolved_duckdb_path = sqlite_db_path.with_suffix(".duckdb")

    limit = (
        rate_limit_per_minute
        if rate_limit_per_minute is not None
        else int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    )
    chat_limit = (
        chat_rate_limit_per_minute
        if chat_rate_limit_per_minute is not None
        else int(os.getenv("CHAT_RATE_LIMIT_PER_MINUTE", "6"))
    )
    daily_chat_limit = (
        chat_daily_limit_per_user
        if chat_daily_limit_per_user is not None
        else int(os.getenv("CHAT_DAILY_LIMIT_PER_USER", "20"))
    )
    limiter = SlidingWindowRateLimiter(max_requests=limit, window_seconds=60)
    browse_limit = max(limit * 3, 180) if limit > 0 else 0
    browse_limiter = SlidingWindowRateLimiter(max_requests=browse_limit, window_seconds=60)
    chat_limiter = SlidingWindowRateLimiter(max_requests=chat_limit, window_seconds=60)
    chat_daily_limiter = SlidingWindowRateLimiter(
        max_requests=daily_chat_limit,
        window_seconds=86_400,
        detail_message=(
            f"Limite diário de {daily_chat_limit} mensagens ao Tutor SQL atingido. "
            "Tente novamente amanhã."
        ),
    )
    schema_lock = Lock()

    def enforce_rate_limit(request: Request) -> None:
        limiter.check(_extract_client_ip(request))

    def enforce_browse_rate_limit(request: Request) -> None:
        browse_limiter.check(_extract_client_ip(request))

    def enforce_chat_rate_limit(request: Request) -> None:
        ip = _extract_client_ip(request)
        chat_limiter.check(ip)
        chat_daily_limiter.check(ip)

    def get_engine_db_path(engine: DatabaseEngine) -> Path:
        if engine == "duckdb":
            return Path(application.state.duckdb_path)
        return Path(application.state.db_path)

    def get_cached_schema(engine: DatabaseEngine = "sqlite") -> list[dict[str, Any]]:
        cached = application.state.schema_cache.get(engine)
        if cached is not None:
            return cached
        with schema_lock:
            cached = application.state.schema_cache.get(engine)
            if cached is None:
                cached = get_schema_metadata(
                    db_path=get_engine_db_path(engine),
                    engine=engine,
                )
                application.state.schema_cache[engine] = cached
            return cached

    @asynccontextmanager
    async def lifespan(app_instance: FastAPI):
        ensure_database(app_instance.state.db_path, engine="sqlite")
        ensure_database(app_instance.state.duckdb_path, engine="duckdb")
        get_cached_schema("sqlite")
        get_cached_schema("duckdb")
        yield

    application = FastAPI(
        title="SQL Arena — Treinamento Interativo de SQL",
        version="2.0.0",
        lifespan=lifespan,
        docs_url=None if is_prod else "/docs",
        redoc_url=None if is_prod else "/redoc",
        openapi_url=None if is_prod else "/openapi.json",
    )
    application.state.db_path = sqlite_db_path
    application.state.duckdb_path = resolved_duckdb_path
    application.state.schema_cache = {"sqlite": None, "duckdb": None}

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
    def health_check() -> dict[str, str]:
        sqlite_file = Path(application.state.db_path)
        duckdb_file = Path(application.state.duckdb_path)
        if not sqlite_file.exists():
            ensure_database(sqlite_file, engine="sqlite")
        if not duckdb_file.exists():
            ensure_database(duckdb_file, engine="duckdb")
        return {"status": "ok"}

    @application.get("/api/schema", response_model=list[TableSchema])
    def get_schema(
        engine: DatabaseEngine = Query("sqlite"),
    ) -> list[TableSchema]:
        return [TableSchema(**table) for table in get_cached_schema(engine)]

    @application.get(
        "/api/tables/{table_name}",
        dependencies=[Depends(enforce_browse_rate_limit)],
    )
    def browse_table(
        table_name: str,
        engine: DatabaseEngine = Query("sqlite"),
        page: int = Query(1, ge=1),
        page_size: int = Query(15, ge=1, le=100),
        search: str = Query("", max_length=100),
        sort_by: str | None = Query(None),
        sort_dir: Literal["asc", "desc"] = Query("asc"),
    ) -> dict[str, Any]:
        """Retorna dados paginados e filtráveis de uma tabela válida do esquema."""
        schema = get_cached_schema(engine)
        table_map = {t["name"]: t for t in schema}
        if table_name not in table_map:
            raise HTTPException(status_code=404, detail="Tabela não encontrada.")

        valid_columns = [c["name"] for c in table_map[table_name]["columns"]]
        order_col = sort_by if sort_by in valid_columns else valid_columns[0]
        order_direction = "DESC" if sort_dir == "desc" else "ASC"

        term = search.strip()
        offset = (page - 1) * page_size
        db_file = get_engine_db_path(engine).resolve()

        if engine == "duckdb":
            ensure_database(db_file, engine="duckdb")
            where_clause = ""
            params: list[Any] = []
            if term:
                escaped = term.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                like_parts = [f'LOWER(CAST("{col}" AS VARCHAR)) LIKE ? ESCAPE \'\\\'' for col in valid_columns]
                where_clause = "WHERE " + " OR ".join(like_parts)
                params.extend([f"%{escaped}%"] * len(valid_columns))

            conn = connect_duckdb_readonly(db_file)
            try:
                total_rows = conn.execute(
                    f'SELECT COUNT(*) FROM "{table_name}" {where_clause}',
                    params,
                ).fetchone()[0]
                raw_rows = conn.execute(
                    f'SELECT * FROM "{table_name}" {where_clause} '
                    f'ORDER BY "{order_col}" {order_direction} LIMIT ? OFFSET ?',
                    [*params, page_size, offset],
                ).fetchall()
                rows = [[_sanitize_cell(cell) for cell in row] for row in raw_rows]
            finally:
                conn.close()
        else:
            ensure_database(db_file, engine="sqlite")
            where_clause = ""
            params = []
            if term:
                escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                like_parts = [f'CAST("{col}" AS TEXT) LIKE ? ESCAPE \'\\\'' for col in valid_columns]
                where_clause = "WHERE " + " OR ".join(like_parts)
                params.extend([f"%{escaped}%"] * len(valid_columns))

            conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
            try:
                conn.execute("PRAGMA query_only = ON;")
                total_rows = conn.execute(
                    f'SELECT COUNT(*) FROM "{table_name}" {where_clause}',
                    params,
                ).fetchone()[0]

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
    def get_challenges(
        nivel: DifficultyLevel | None = Query(None),
        engine: DatabaseEngine = Query("sqlite"),
    ) -> list[ChallengeSummary]:
        return [_to_challenge_summary(ch, engine=engine) for ch in list_challenges(nivel)]

    @application.post(
        "/api/execute",
        response_model=ExecuteQueryResponse,
        dependencies=[Depends(enforce_rate_limit)],
    )
    def execute_query(payload: QueryPayload) -> ExecuteQueryResponse:
        engine = payload.engine
        current_db = get_engine_db_path(engine)

        if payload.challenge_id is None:
            try:
                user_res = execute_readonly_sql(
                    payload.sql,
                    db_path=current_db,
                    engine=engine,
                )
                return ExecuteQueryResponse(
                    mode="free",
                    engine=engine,
                    user_result=_to_table_result(user_res),
                )
            except (SQLValidationError, sqlite3.Error, duckdb.Error, TimeoutError) as exc:
                return ExecuteQueryResponse(
                    mode="free",
                    engine=engine,
                    user_error=str(exc),
                    user_error_hint=translate_sql_error(str(exc), engine=engine),
                )

        challenge = get_challenge(payload.challenge_id)
        if challenge is None:
            raise HTTPException(status_code=404, detail="Desafio não encontrado.")

        expected_sql = challenge.get_solution(engine)
        expected_res = execute_readonly_sql(
            expected_sql,
            db_path=current_db,
            engine=engine,
        )
        expected_answer = ExpectedAnswer(
            sql=expected_sql,
            result=_to_table_result(expected_res),
        )

        try:
            user_res = execute_readonly_sql(
                payload.sql,
                db_path=current_db,
                engine=engine,
            )
        except (SQLValidationError, sqlite3.Error, duckdb.Error, TimeoutError) as exc:
            return ExecuteQueryResponse(
                mode="challenge",
                engine=engine,
                challenge_id=challenge.id,
                user_error=str(exc),
                user_error_hint=translate_sql_error(str(exc), engine=engine),
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
            engine=engine,
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
    def explain_query(payload: QueryPayload) -> dict[str, Any]:
        """Retorna o plano de execução SQLite ou DuckDB para fins didáticos."""
        engine = payload.engine
        try:
            res = explain_readonly_sql(
                payload.sql,
                db_path=get_engine_db_path(engine),
                engine=engine,
            )
            return {"result": _to_table_result(res), "error": None}
        except (SQLValidationError, sqlite3.Error, duckdb.Error, TimeoutError) as exc:
            return {"result": None, "error": str(exc)}

    @application.get("/api/chat/status")
    def chat_status() -> dict[str, Any]:
        """Informa se o agente tutor (Gemini) está configurado no servidor e seus limites."""
        api_key, model, fallback_models = get_tutor_config()
        max_output_tokens, thinking_level, max_history = get_tutor_limits()
        return {
            "enabled": bool(api_key),
            "model": model,
            "fallback_models": fallback_models,
            "daily_limit": daily_chat_limit,
            "rate_limit_per_minute": chat_limit,
            "max_output_tokens": max_output_tokens,
            "thinking_level": thinking_level,
            "max_history_messages": max_history,
        }

    @application.post(
        "/api/chat",
        response_model=ChatResponse,
        dependencies=[Depends(enforce_chat_rate_limit)],
    )
    def chat_with_tutor(payload: ChatPayload, request: Request) -> ChatResponse:
        """Encaminha dúvida de SQL + contexto atual do usuário para o agente Google Gemini."""
        challenge = None
        if payload.challenge_id:
            challenge = get_challenge(payload.challenge_id)
            if challenge is None:
                raise HTTPException(status_code=404, detail="Desafio não encontrado.")

        try:
            reply, model = ask_gemini_tutor(
                payload=payload,
                schema=get_cached_schema(payload.engine),
                challenge=challenge,
            )
            remaining_daily = chat_daily_limiter.remaining(_extract_client_ip(request))
            return ChatResponse(reply=reply, model=model, remaining_daily=remaining_daily)
        except TutorConfigError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except TutorUpstreamError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    return application


def _load_local_dotenv() -> None:
    """Carrega variáveis do arquivo .env local quando não definidas no ambiente."""
    if "pytest" in sys.modules:
        return
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if not env_file.is_file():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


_load_local_dotenv()
app = create_app()
