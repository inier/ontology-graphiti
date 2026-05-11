FROM localhost/python:3.10-slim

WORKDIR /app

RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ && rm -rf /var/lib/apt/lists/*

# 先复制依赖文件，利用 Docker 缓存
COPY requirements.txt ./
COPY openharness/pyproject.toml ./openharness/pyproject.toml

# 安装依赖（缓存友好）
RUN pip install --no-cache-dir \
    uvicorn[standard] \
    fastapi \
    pydantic \
    pymongo \
    networkx \
    python-dateutil \
    httpx \
    starlette \
    python-multipart \
    neo4j \
    redis \
    python-jose[cryptography] \
    jsonpickle \
    opa-python \
    celery || true

RUN pip install --no-cache-dir -r requirements.txt || true

RUN pip install --no-cache-dir -e ./openharness || true

# 最后复制代码（代码变化不影响依赖缓存）
COPY . .

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]