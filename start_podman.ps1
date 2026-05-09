Write-Host "=== ODAP Startup Script (Using daocloud mirror) ==="
Write-Host ""

$MIRROR="docker.m.daocloud.io"

Write-Host "1. Creating network"
podman network create graphiti-network 2>&1 | Out-Null

Write-Host "2. Pulling Redis"
podman pull $MIRROR/library/redis:6

Write-Host "3. Pulling MongoDB"
podman pull $MIRROR/library/mongo:latest

Write-Host "4. Pulling Neo4j"
podman pull $MIRROR/library/neo4j:latest

Write-Host "5. Pulling OPA"
podman pull $MIRROR/openpolicyagent/opa:0.58.0

Write-Host "6. Tagging images"
podman tag $MIRROR/library/redis:6 redis:6
podman tag $MIRROR/library/mongo:latest mongo:latest
podman tag $MIRROR/library/neo4j:latest neo4j:latest
podman tag $MIRROR/openpolicyagent/opa:0.58.0 openpolicyagent/opa:0.58.0

Write-Host "7. Starting Redis"
podman run -d --name graphiti-cache -p 6379:6379 --network graphiti-network redis:6

Write-Host "8. Starting MongoDB"
podman run -d --name graphiti-mongodb -p 27017:27017 --network graphiti-network mongo:latest

Write-Host "9. Starting Neo4j"
podman run -d --name graphiti-neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/neo4j123456 -e NEO4J_dbms_memory_heap_max__size=2G --network graphiti-network neo4j:latest

Write-Host "10. Starting OPA"
podman run -d --name graphiti-policy-service -p 8181:8181 -v e:\DEMO\AI\ontology-graphiti\odap\infra\opa\policies:/policies --network graphiti-network openpolicyagent/opa:0.58.0 run --server --log-level=info --set=decision_logs.console=true

Write-Host "11. Waiting for services to start"
Start-Sleep -Seconds 5

Write-Host "12. Building main application"
cd e:\DEMO\AI\ontology-graphiti
podman build -t graphiti-app:latest -f docker/Dockerfile .

Write-Host "13. Starting main application"
podman run -d --name graphiti-main-app -p 8000:8000 -e IN_DOCKER=true -e NEO4J_URI=bolt://graphiti-neo4j:7687 -e OPA_URL=http://graphiti-policy-service:8181 -e REDIS_URL=redis://graphiti-cache:6379 -e MONGODB_URI=mongodb://graphiti-mongodb:27017 -v e:\DEMO\AI\ontology-graphiti:/app --network graphiti-network graphiti-app:latest

Write-Host ""
Write-Host "=== Startup Complete ==="
podman ps