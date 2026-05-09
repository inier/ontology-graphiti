@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

rem ============================================================
rem  Graphiti 一键启动/停止脚本
rem  基于 podman-compose-win-fix.py 修复 Windows 路径问题
rem
rem  用法:
rem    graphiti up        启动所有服务（前端+后端）
rem    graphiti down      停止所有服务
rem    graphiti restart   重启所有服务
rem    graphiti rebuild   重新构建并启动
rem    graphiti status    查看服务状态
rem    graphiti logs      查看后端日志
rem    graphiti pull      拉取基础镜像
rem ============================================================

set "PROJECT_ROOT=%~dp0"
set "DOCKER_DIR=%PROJECT_ROOT%docker"
set "COMPOSE_FILE=%DOCKER_DIR%\docker-compose.yml"
set "WIN_FIX=%DOCKER_DIR%\podman-compose-win-fix.py"
set "PYTHON_EXE=C:\Users\changan\miniconda3\python.exe"
set "MIRROR=docker.m.daocloud.io"

if "%1"=="" set "ACTION=up" & goto :run
set "ACTION=%1"

:check_action
if /I "%ACTION%"=="up"      goto :up
if /I "%ACTION%"=="down"    goto :down
if /I "%ACTION%"=="restart" goto :restart
if /I "%ACTION%"=="rebuild" goto :rebuild
if /I "%ACTION%"=="status"  goto :status
if /I "%ACTION%"=="logs"    goto :logs
if /I "%ACTION%"=="pull"    goto :pull
if /I "%ACTION%"=="-h"      goto :help
if /I "%ACTION%"=="--help"  goto :help
if /I "%ACTION%"=="/?"      goto :help
echo [ERROR] Unknown action: %ACTION%
goto :help

rem ============================================================
:up
echo.
echo ========================================
echo   启动 Graphiti 服务（前端+后端）
echo ========================================
echo.

echo [1] 构建并启动所有服务...
pushd "%DOCKER_DIR%"
"%PYTHON_EXE%" "%WIN_FIX%" -f "%COMPOSE_FILE%" up -d --build 2>&1 | findstr /V "SyntaxWarning"
popd

echo [2] 等待服务就绪（15秒）...
timeout /t 15 /nobreak >nul

echo.
echo ========================================
echo   服务访问地址
echo ========================================
echo.
echo   前端界面:  http://localhost:80
echo   后端 API:  http://localhost:8000
echo   API 文档:  http://localhost:8000/docs
echo   健康检查:  http://localhost:8000/health
echo   Neo4j:     http://localhost:7474
echo   OPA:       http://localhost:8181
echo   Redis:     localhost:6379
echo   MongoDB:   localhost:27017
echo.

call :show_status
goto :eof

rem ============================================================
:down
echo.
echo ========================================
echo   停止 Graphiti 服务
echo ========================================
echo.
pushd "%DOCKER_DIR%"
"%PYTHON_EXE%" "%WIN_FIX%" -f "%COMPOSE_FILE%" down 2>&1 | findstr /V "SyntaxWarning"
popd
echo   已停止所有服务.
goto :eof

rem ============================================================
:restart
echo.
echo ========================================
echo   重启 Graphiti 服务
echo ========================================
call :down
call :up
goto :eof

rem ============================================================
:rebuild
echo.
echo ========================================
echo   重建 Graphiti 服务
echo ========================================
call :down
echo [0] 清理旧镜像...
podman rmi localhost/docker_app:latest 2>nul
podman rmi localhost/docker_frontend:latest 2>nul
echo   已清理.
call :up
goto :eof

rem ============================================================
:status
echo.
call :show_status
goto :eof

rem ============================================================
:logs
set "TARGET=graphiti-main-app"
if /I "%2"=="fe"      set "TARGET=graphiti-frontend"
if /I "%2"=="frontend" set "TARGET=graphiti-frontend"
if /I "%2"=="neo4j"   set "TARGET=graphiti-neo4j"
if /I "%2"=="mongo"   set "TARGET=graphiti-mongodb"
if /I "%2"=="redis"   set "TARGET=graphiti-cache"
if /I "%2"=="opa"     set "TARGET=graphiti-policy-service"
if /I "%2"=="app"     set "TARGET=graphiti-main-app"
echo [INFO] Showing logs for %TARGET% ^(Ctrl+C to exit^)...
podman logs -f --tail 50 %TARGET%
goto :eof

rem ============================================================
:pull
echo.
echo ========================================
echo   拉取基础镜像（使用 DaoCloud 镜像源）
echo ========================================
echo.
set /a COUNT=1
call :pull_one %COUNT% %MIRROR%/library/redis:6                     localhost/redis:6
set /a COUNT+=1
call :pull_one %COUNT% %MIRROR%/library/mongo:latest                localhost/mongo:latest
set /a COUNT+=1
call :pull_one %COUNT% %MIRROR%/library/neo4j:latest                localhost/neo4j:latest
set /a COUNT+=1
call :pull_one %COUNT% %MIRROR%/openpolicyagent/opa:0.58.0           localhost/openpolicyagent/opa:0.58.0
set /a COUNT+=1
call :pull_one %COUNT% %MIRROR%/library/python:3.10-slim             localhost/python:3.10-slim
set /a COUNT+=1
call :pull_one %COUNT% %MIRROR%/library/node:20-alpine               localhost/node:20-alpine
set /a COUNT+=1
call :pull_one %COUNT% %MIRROR%/library/nginx:alpine                 localhost/nginx:alpine
echo.
echo   基础镜像拉取完成.
goto :eof

:help
echo.
echo ========================================
echo   Graphiti 一键启动/停止脚本
echo ========================================
echo.
echo 用法: graphiti ^<action^>
echo.
echo   up        启动所有服务（前端+后端）
echo   down      停止所有服务
echo   restart   重启所有服务
echo   rebuild   重新构建并启动
echo   status    查看服务状态
echo   logs      查看后端日志（可用: fe/neo4j/mongo/redis/opa）
echo   pull      拉取基础镜像
echo.
echo 示例:
echo   graphiti up
echo   graphiti down
echo   graphiti logs fe
echo.
goto :eof

rem ============================================================
:show_status
echo ========================================
echo   容器状态
echo ========================================
podman ps -a --filter "name=graphiti" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>nul
echo.
goto :eof

:check_container
set "EXISTS="
for /f "tokens=*" %%c in ('podman ps -a --filter "name=%2" --format "{{.Names}}" 2^>nul') do set "EXISTS=%%c"
if defined EXISTS (
    echo [%1] %2 - already exists
    echo     OK: skipped
) else (
    echo [%1] Pulling %2 ...
    podman pull %3 2>&1
    podman tag %3 %4 2>nul
    echo     OK: %4 pulled
)
goto :eof

:pull_one
set "FLAG="
for /f "tokens=*" %%c in ('podman images --format "{{.Repository}}:{{.Tag}}" 2^>nul ^| findstr /C:"%~4" 2^>nul') do set "FLAG=%%c"
if defined FLAG (
    echo [%1] %~4 - already exists, skipped
) else (
    echo [%1] Pulling %~4 ...
    podman pull %~2
    podman tag %~2 %~3
    echo     OK: %~4 pulled
)
goto :eof