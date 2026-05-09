FROM localhost/python:3.10-slim

WORKDIR /app

RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ && rm -rf /var/lib/apt/lists/*

COPY . .

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

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
