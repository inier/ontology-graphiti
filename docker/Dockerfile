FROM localhost/python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV ENVIRONMENT production

RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    && rm -rf /var/lib/apt/lists/*

# 先复制 openharness 子模块（requirements.txt 依赖它）
COPY openharness ./openharness

# 复制 hyper-extract 子模块（requirements.txt 依赖它）
COPY hyper-extract ./hyper-extract

# M6 fix: 统一使用 requirements.txt 作为依赖单一事实来源。
# 移除所有 || echo WARNING，安装失败时构建直接中断（fail-fast），
# 避免生产镜像缺失关键依赖（如 pyjwt/bcrypt）却在启动时才崩溃。
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# graphiti-core 单独安装：该包可能因网络/平台问题失败，
# 失败时降级到 Neo4j Driver 模式（GraphManager 内部已处理 fallback）。
# 此处保留容错是因为 graphiti-core 不是运行时硬依赖，缺失时系统仍可启动。
RUN pip install --no-cache-dir graphiti-core || echo "WARNING: graphiti-core install failed, falling back to Neo4j Driver mode (non-fatal)"

COPY . .

RUN mkdir -p /app/data

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "odap.web.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
