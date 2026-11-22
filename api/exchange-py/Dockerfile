# Exchange (FastAPI sobre a PTAX do BCB), como pede a página "API de Câmbio: serviço do BACEN"
FROM python:3.12-slim

# binário do uv copiado da imagem oficial, com versão fixa (build reprodutível); o uvx não é usado
COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# dependências antes do código: mudar o main.py não reinstala nada (cache da camada)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY main.py ./

# roda sem root (UID numérico: o runAsNonRoot do Kubernetes consegue conferir)
RUN useradd --uid 10001 --user-group --no-create-home --shell /usr/sbin/nologin exchange
USER 10001

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
