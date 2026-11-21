FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    PORT=7500 \
    HOME=/tmp \
    TMPDIR=/tmp \
    SQLITE_TMPDIR=/tmp

WORKDIR /app

# Instala apenas as dependências necessárias para produção
COPY requirements-prod.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements-prod.txt

# Cria usuário não-root para executar a aplicação
RUN groupadd --system appgroup \
    && useradd --system --gid appgroup --no-create-home appuser

# Copia a aplicação e gera as bases SQLite e DuckDB em modo somente leitura para o appuser
COPY app/ ./app/
RUN python -m app.database \
    && chown -R root:appgroup /app \
    && chmod 444 /app/data/escola.db /app/data/escola.duckdb \
    && chmod 555 /app/data

USER appuser

EXPOSE 7500

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7500/api/health', timeout=3)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7500", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
