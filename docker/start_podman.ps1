param(
    [string]$Action = "up"
)

$ProjectRoot = "e:\DEMO\AI\ontology-graphiti"
$NetworkName = "graphiti-network"

function Show-Status {
    Write-Host "`n=== Container Status ===" -ForegroundColor Cyan
    podman ps --format "table {{.Names}}`t{{.Status}}`t{{.Ports}}" --filter "name=graphiti"
    Write-Host ""
}

function Start-Services {
    Write-Host "=== Starting Graphiti Services ===" -ForegroundColor Green

    $networkExists = podman network exists $NetworkName 2>$null
    if (-not $networkExists) {
        Write-Host "Creating network: $NetworkName" -ForegroundColor Yellow
        podman network create $NetworkName
    }

    $running = podman ps --filter "name=graphiti-mongodb" --format "{{.Names}}" 2>$null
    if ($running) {
        Write-Host "Services already running. Use 'down' first to restart." -ForegroundColor Yellow
        Show-Status
        return
    }

    Write-Host "Starting MongoDB..." -ForegroundColor Yellow
    podman run -d --name graphiti-mongodb --network $NetworkName -p 27017:27017 -v mongodb-data:/data/db localhost/mongo:latest

    Write-Host "Starting Redis..." -ForegroundColor Yellow
    podman run -d --name graphiti-cache --network $NetworkName -p 6379:6379 -v redis-data:/data localhost/redis:6

    Write-Host "Starting Neo4j..." -ForegroundColor Yellow
    podman run -d --name graphiti-neo4j --network $NetworkName -p 7474:7474 -p 7687:7687 `
        -e NEO4J_AUTH=neo4j/neo4j123456 `
        -e NEO4J_dbms_memory_heap_max__size=2G `
        -e NEO4J_dbms_security_procedures_unrestricted=apoc.* `
        -v neo4j-data:/data localhost/neo4j:latest

    Write-Host "Starting OPA Policy Service..." -ForegroundColor Yellow
    podman run -d --name graphiti-policy-service --network $NetworkName -p 8181:8181 `
        -v "${ProjectRoot}\odap\infra\opa:/policies" `
        localhost/openpolicyagent/opa:0.58.0 run --server --log-level=info --set=decision_logs.console=true /policies

    Write-Host "Waiting for infrastructure services (10s)..." -ForegroundColor Yellow
    Start-Sleep -Seconds 10

    $appImage = podman images --filter "reference=localhost/graphiti-app" --format "{{.Repository}}:{{.Tag}}" 2>$null
    if (-not $appImage) {
        $appImage = podman images --filter "reference=localhost/test-build" --format "{{.Repository}}:{{.Tag}}" 2>$null
    }
    if (-not $appImage) {
        Write-Host "Building app image..." -ForegroundColor Yellow
        podman build -t localhost/graphiti-app:latest -f "${ProjectRoot}\docker\Dockerfile" $ProjectRoot
        $appImage = "localhost/graphiti-app:latest"
    }

    Write-Host "Starting App..." -ForegroundColor Yellow
    podman run -d --name graphiti-main-app --network $NetworkName -p 8000:8000 `
        --env-file "${ProjectRoot}\.env.docker" `
        -e IN_DOCKER=true `
        -e NEO4J_URI=bolt://graphiti-neo4j:7687 `
        -e NEO4J_USER=neo4j `
        -e NEO4J_PASSWORD=neo4j123456 `
        -e OPA_URL=http://graphiti-policy-service:8181 `
        -e REDIS_URL=redis://graphiti-cache:6379 `
        -e MONGODB_URI=mongodb://graphiti-mongodb:27017 `
        -e CORS_ORIGINS=http://localhost:5173,http://localhost:8000,http://localhost:80 `
        -v app-data:/app/data `
        $appImage

    Write-Host "Waiting for app to start (15s)..." -ForegroundColor Yellow
    Start-Sleep -Seconds 15

    Show-Status

    Write-Host "=== Service URLs ===" -ForegroundColor Green
    Write-Host "  API:      http://localhost:8000" -ForegroundColor White
    Write-Host "  Health:   http://localhost:8000/health" -ForegroundColor White
    Write-Host "  Neo4j:    http://localhost:7474" -ForegroundColor White
    Write-Host "  OPA:      http://localhost:8181" -ForegroundColor White
    Write-Host "  Redis:    localhost:6379" -ForegroundColor White
    Write-Host "  MongoDB:  localhost:27017" -ForegroundColor White
}

function Stop-Services {
    Write-Host "=== Stopping Graphiti Services ===" -ForegroundColor Red

    $containers = @("graphiti-main-app", "graphiti-policy-service", "graphiti-neo4j", "graphiti-cache", "graphiti-mongodb")
    foreach ($c in $containers) {
        $exists = podman ps -a --filter "name=$c" --format "{{.Names}}" 2>$null
        if ($exists) {
            Write-Host "Stopping and removing $c..." -ForegroundColor Yellow
            podman stop $c 2>$null
            podman rm $c 2>$null
        }
    }

    Write-Host "Services stopped." -ForegroundColor Green
}

switch ($Action) {
    "up"    { Start-Services }
    "down"  { Stop-Services }
    "status"{ Show-Status }
    default { Write-Host "Usage: .\start_podman.ps1 -Action [up|down|status]" -ForegroundColor Yellow }
}
