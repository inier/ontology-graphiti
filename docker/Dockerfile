FROM localhost/python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV ENVIRONMENT production
ENV UV_PROJECT_ENVIRONMENT=/usr/local
ENV UV_LINK_MODE=copy

RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 切换 apt 到清华 HTTPS 镜像源。
# 网络环境：Podman (WSL) TCP 80 不通但 443 可用（PyPI HTTPS 能装包），
# 故必须用 HTTPS。Debian trixie deb822 格式在 /etc/apt/sources.list.d/debian.sources，
# 也兼容旧格式 /etc/apt/sources.list，sed 同时处理并改 https。
#
# 容错说明：apt 镜像偶发不可达时，gcc/tesseract 安装可能失败。
# 多数 Python 包已提供 manylinux 预编译 wheel，不依赖 gcc；
# tesseract-ocr 仅 OCR 功能需要，不影响核心 API 和测试运行。
# 故用 || true 容错：apt 失败不阻断构建，uv sync 阶段如遇需编译的包会明确报错。
RUN sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g; s|security.debian.org|mirrors.tuna.tsinghua.edu.cn|g; s| http://| https://|g' \
        /etc/apt/sources.list.d/debian.sources /etc/apt/sources.list 2>/dev/null || true \
    && (apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        tesseract-ocr \
        tesseract-ocr-chi-sim \
        && rm -rf /var/lib/apt/lists/* \
    || echo "WARN: apt install failed (network), relying on pre-built wheels")

# 固定 uv 版本，避免 uv.lock 与 uv 版本不匹配导致 --frozen 解析失败
# 网络容错：清华 PyPI 镜像偶发超时，用 PIP_DEFAULT_TIMEOUT + 重试循环
ARG UV_VERSION=0.5.11
ENV PIP_DEFAULT_TIMEOUT=600
RUN for i in 1 2 3 4 5; do \
        pip install uv==${UV_VERSION} && break || echo "pip retry $i..." && sleep 3; \
    done

# ─── 阶段 1：复制 workspace 元数据（层缓存友好） ───
COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml ./apps/api/
COPY packages/openharness/pyproject.toml ./packages/openharness/
COPY packages/hyper-extract/pyproject.toml ./packages/hyper-extract/

# 子模块源码（editable install 需要）
COPY packages/openharness ./packages/openharness
COPY packages/hyper-extract ./packages/hyper-extract

# ─── 阶段 2：安装依赖 ───
# graphiti-core 已是必需依赖（apps/api/pyproject.toml），uv sync 会一并安装
# 关键：用 --package odap 安装 odap 及其 workspace 依赖（hyperextract/openharness），
# 用 --no-dev 跳过 dev 组（mkdocs-material/babel 等大包），减少网络压力。
# 测试依赖（pytest 等）单独安装，因为它们是小包更容易下载成功。
ENV UV_HTTP_TIMEOUT=600
ENV UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
# 网络容错：清华镜像偶发 connection reset，用重试循环（正确版：失败时 exit 1）
RUN set -e; \
    SYNC_OK=0; \
    for i in 1 2 3 4 5 6 7 8; do \
        if uv sync --frozen --package odap --no-dev; then \
            SYNC_OK=1; break; \
        fi; \
        echo "uv sync retry $i..."; sleep 3; \
    done; \
    if [ "$SYNC_OK" = "0" ]; then echo "FATAL: uv sync failed after 8 retries"; exit 1; fi
# 单独安装测试依赖（小包，容易成功）
# 注意：UV_PROJECT_ENVIRONMENT=/usr/local 是系统 Python，无 venv，需 --system
RUN set -e; \
    PIP_OK=0; \
    for i in 1 2 3 4 5; do \
        if uv pip install --system pytest pytest-asyncio pytest-mock; then \
            PIP_OK=1; break; \
        fi; \
        echo "pip install retry $i..."; sleep 3; \
    done; \
    if [ "$PIP_OK" = "0" ]; then echo "FATAL: pip install failed after 5 retries"; exit 1; fi

# ─── 阶段 3：复制后端源码（最常变，放最后） ───
COPY apps/api/odap ./apps/api/odap
COPY apps/api/main.py ./apps/api/main.py

RUN mkdir -p /app/data

EXPOSE 8000

WORKDIR /app/apps/api
CMD ["python", "-m", "uvicorn", "odap.web.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
