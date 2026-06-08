FROM localhost/python:3.10-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV ENVIRONMENT production

RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./

RUN pip install --no-cache-dir fastapi pydantic uvicorn[standard] httpx starlette python-multipart || echo "WARNING: core web packages install had issues"
RUN pip install --no-cache-dir neo4j networkx redis python-dateutil || echo "WARNING: data packages install had issues"
RUN pip install --no-cache-dir python-jose[cryptography] pyjwt bcrypt jsonpickle opa-python celery || echo "WARNING: infra packages install had issues"
RUN pip install --no-cache-dir openai pyyaml aiohttp || echo "WARNING: util packages install had issues"

RUN pip install --no-cache-dir graphiti-core || echo "WARNING: graphiti-core install failed, falling back to Neo4j Driver mode"

COPY . .

RUN pip install --no-cache-dir -e ./openharness || echo "WARNING: openharness install failed, using mock mode"

RUN mkdir -p /app/data

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "odap.web.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
