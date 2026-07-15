FROM localhost/python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV ENVIRONMENT production
ENV UV_PROJECT_ENVIRONMENT=/usr/local
ENV UV_LINK_MODE=copy

RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

# ─── 阶段 1：复制 workspace 元数据（层缓存友好） ───
COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml ./apps/api/
COPY packages/openharness/pyproject.toml ./packages/openharness/
COPY packages/hyper-extract/pyproject.toml ./packages/hyper-extract/

# 子模块源码（editable install 需要）
COPY packages/openharness ./packages/openharness
COPY packages/hyper-extract ./packages/hyper-extract

# ─── 阶段 2：安装依赖 ───
RUN uv sync --frozen --no-dev --package odap

# graphiti-core 容错（保持原版降级行为）
RUN pip install --no-cache-dir graphiti-core \
    || echo "WARNING: graphiti-core install failed, fallback to Neo4j Driver mode (non-fatal)"

# ─── 阶段 3：复制后端源码（最常变，放最后） ───
COPY apps/api/odap ./apps/api/odap
COPY apps/api/main.py ./apps/api/main.py

RUN mkdir -p /app/data

EXPOSE 8000

WORKDIR /app/apps/api
CMD ["python", "-m", "uvicorn", "odap.web.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
