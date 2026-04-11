"""
基于FastAPI的异步网页对话界面
实现战场态势对话功能
"""

import sys
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.orchestrator import SelfCorrectingOrchestrator
from core.graph_manager import BattlefieldGraphManager

orchestrator = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global orchestrator
    orchestrator = SelfCorrectingOrchestrator(user_role="pilot")
    print(f"系统初始化完成，用户角色: pilot")
    yield
    print("关闭系统")

app = FastAPI(
    title="战场指挥系统",
    description="基于 Graphiti + OPA + Skill 的智能战场决策平台",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HTML_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>战场指挥系统</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: linear-gradient(135deg, #1a1a2e, #16213e); min-height: 100vh; color: #fff; }
        .container { max-width: 900px; margin: 0 auto; padding: 20px; }
        header { text-align: center; padding: 30px 0; border-bottom: 1px solid rgba(255,255,255,0.1); }
        header h1 { font-size: 2.5em; background: linear-gradient(90deg, #00d4ff, #7b2ff7); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .role-selector { display: flex; justify-content: center; gap: 15px; margin: 20px 0; }
        .role-btn { padding: 10px 25px; border: 2px solid #7b2ff7; background: transparent; color: #fff; border-radius: 25px; cursor: pointer; font-size: 14px; }
        .role-btn.active, .role-btn:hover { background: #7b2ff7; }
        .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 20px 0; }
        .stat-card { background: rgba(255,255,255,0.05); padding: 15px; border-radius: 10px; text-align: center; }
        .stat-card .number { font-size: 2em; background: linear-gradient(90deg, #00d4ff, #7b2ff7); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .stat-card .label { color: #888; font-size: 0.8em; }
        .quick-commands { display: flex; flex-wrap: wrap; gap: 10px; margin: 20px 0; justify-content: center; }
        .quick-cmd { padding: 8px 16px; background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); border-radius: 20px; color: #fff; cursor: pointer; font-size: 12px; }
        .quick-cmd:hover { background: rgba(255,255,255,0.2); }
        .chat-container { background: rgba(255,255,255,0.05); border-radius: 15px; padding: 20px; margin: 20px 0; max-height: 400px; overflow-y: auto; }
        .message { margin-bottom: 15px; padding: 12px 16px; border-radius: 10px; }
        .message.user { background: rgba(0,212,255,0.2); margin-left: 50px; }
        .message.assistant { background: rgba(123,47,247,0.2); margin-right: 50px; }
        .message.system { background: rgba(255,255,255,0.05); color: #888; }
        .message.error { background: rgba(255,0,0,0.2); color: #ff6b6b; }
        .input-container { display: flex; gap: 10px; margin: 20px 0; }
        .input-container input { flex: 1; padding: 15px; border: 2px solid rgba(255,255,255,0.1); background: rgba(255,255,255,0.05); border-radius: 25px; color: #fff; font-size: 16px; }
        .input-container input:focus { outline: none; border-color: #7b2ff7; }
        .input-container button { padding: 15px 30px; background: linear-gradient(90deg, #00d4ff, #7b2ff7); border: none; border-radius: 25px; color: #fff; cursor: pointer; font-size: 16px; }
        footer { text-align: center; padding: 20px; color: #666; font-size: 0.8em; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎯 战场指挥系统</h1>
            <p>基于 Graphiti + OPA + Skill 的智能战场决策平台</p>
        </header>

        <div class="role-selector">
            <button class="role-btn active" onclick="switchRole('pilot')">🛩️ 飞行员</button>
            <button class="role-btn" onclick="switchRole('commander')">🎖️ 指挥官</button>
            <button class="role-btn" onclick="switchRole('intelligence_analyst')">📡 情报分析员</button>
        </div>

        <div class="stats">
            <div class="stat-card"><div class="number" id="totalEntities">-</div><div class="label">战场实体</div></div>
            <div class="stat-card"><div class="number" id="totalRadars">-</div><div class="label">雷达总数</div></div>
            <div class="stat-card"><div class="number" id="totalUnits">-</div><div class="label">军事单位</div></div>
            <div class="stat-card"><div class="number" id="conversationCount">0</div><div class="label">对话轮次</div></div>
        </div>

        <div class="quick-commands" id="quickCommands"></div>

        <div class="chat-container" id="chatContainer">
            <div class="message system">您好，我是战场指挥系统的AI助手。请选择您的角色，然后输入您的指令。</div>
        </div>

        <div class="input-container">
            <input type="text" id="userInput" placeholder="输入您的命令..." onkeypress="if(event.key==='Enter')sendMessage()">
            <button onclick="sendMessage()">发送</button>
        </div>

        <footer><p>Powered by Graphiti Knowledge Graph | OPA Policy Engine | Skill Architecture</p></footer>
    </div>

<script>
var currentRole = 'pilot';
var conversationCount = 0;

var roleCommands = {
    'pilot': [
        { cmd: '帮我看看A区有没有雷达', icon: '🔍', name: 'A区雷达' },
        { cmd: '帮我看看B区有没有雷达', icon: '🔍', name: 'B区雷达' },
        { cmd: '分析当前战场态势', icon: '📊', name: '战场态势' }
    ],
    'commander': [
        { cmd: '推荐打击目标', icon: '🎯', name: '打击推荐' },
        { cmd: '攻击 WEAPON_Re_1', icon: '💥', name: '执行攻击' },
        { cmd: '分析力量对比', icon: '⚔️', name: '力量对比' }
    ],
    'intelligence_analyst': [
        { cmd: '生成战场态势报告', icon: '📋', name: '态势报告' },
        { cmd: '分析当前战场态势', icon: '📊', name: '战场态势' }
    ]
};

function switchRole(role) {
    currentRole = role;
    document.querySelectorAll('.role-btn').forEach(function(btn) { btn.classList.remove('active'); });
    event.target.classList.add('active');
    updateQuickCommands();
    addMessage('system', '角色已切换为: ' + role);
    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/set_role', true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.send(JSON.stringify({role: role}));
}

function updateQuickCommands() {
    var container = document.getElementById('quickCommands');
    var commands = roleCommands[currentRole] || [];
    container.innerHTML = '';
    commands.forEach(function(cmd) {
        var btn = document.createElement('button');
        btn.className = 'quick-cmd';
        btn.innerHTML = cmd.icon + ' ' + cmd.name;
        btn.onclick = function() { executeCommand(cmd.cmd); };
        container.appendChild(btn);
    });
}

function executeCommand(cmd) {
    document.getElementById('userInput').value = cmd;
    sendMessage();
}

function addMessage(type, content) {
    var container = document.getElementById('chatContainer');
    var div = document.createElement('div');
    div.className = 'message ' + type;
    if (Array.isArray(content)) {
        var html = '<div style="margin:5px 0;">';
        content.forEach(function(item, idx) {
            if (item.id) {
                html += '<div style="background:rgba(255,255,255,0.05);padding:10px;margin:5px 0;border-radius:8px;">';
                html += '<strong style="color:#00d4ff;">' + (idx + 1) + '. ' + item.id + '</strong>';
                html += ' <span style="color:#888;">(' + (item.type || 'Unknown') + ')</span><br>';
                var props = item.properties || {};
                for (var key in props) {
                    if (key !== 'entity_type' && key !== 'type') {
                        html += '<span style="color:#aaa;">' + key + ':</span> ' + props[key] + '<br>';
                    }
                }
                html += '</div>';
            } else {
                html += '<div>' + JSON.stringify(item) + '</div>';
            }
        });
        html += '</div>';
        div.innerHTML = html;
    } else if (typeof content === 'object') {
        div.innerHTML = '<pre style="white-space:pre-wrap;word-wrap:break-word;">' + JSON.stringify(content, null, 2) + '</pre>';
    } else {
        div.innerHTML = String(content).replace(/\\n/g, '<br>');
    }
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function sendMessage() {
    var input = document.getElementById('userInput');
    var message = input.value.trim();
    if (!message) return;

    addMessage('user', message);
    input.value = '';
    conversationCount++;
    document.getElementById('conversationCount').textContent = conversationCount;

    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/chat', true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.onreadystatechange = function() {
        if (xhr.readyState === 4) {
            if (xhr.status === 200) {
                var data = JSON.parse(xhr.responseText);
                addMessage('assistant', data.response || data.result);
            } else {
                addMessage('error', '请求失败: ' + xhr.status);
            }
        }
    };
    xhr.send(JSON.stringify({message: message, role: currentRole}));
}

function updateStats() {
    var xhr = new XMLHttpRequest();
    xhr.open('GET', '/get_stats', true);
    xhr.onreadystatechange = function() {
        if (xhr.readyState === 4 && xhr.status === 200) {
            var data = JSON.parse(xhr.responseText);
            document.getElementById('totalEntities').textContent = data.total_entities || 0;
            document.getElementById('totalRadars').textContent = data.entity_types ? (data.entity_types.WeaponSystem || 0) : 0;
            document.getElementById('totalUnits').textContent = data.entity_types ? (data.entity_types.MilitaryUnit || 0) : 0;
        }
    };
    xhr.send();
}

updateQuickCommands();
updateStats();
setInterval(updateStats, 10000);
</script>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(content=HTML_PAGE)

@app.post("/chat")
async def chat(request: Request):
    global orchestrator
    data = await request.json()
    message = data.get('message', '')
    role = data.get('role', 'pilot')

    if orchestrator is None:
        return JSONResponse(content={'response': '系统正在初始化中，请稍后...', 'type': 'error'})

    result = orchestrator.run(message)

    if isinstance(result, list):
        response = result if len(result) > 0 else "未找到匹配的结果"
    elif isinstance(result, dict):
        if result.get('status') == 'denied':
            response = result.get('message', '权限不足')
        else:
            response = result
    else:
        response = str(result) if result else "未找到匹配的结果"

    return JSONResponse(content={'response': response, 'type': 'success', 'result': result})

@app.post("/set_role")
async def set_role(request: Request):
    global orchestrator
    data = await request.json()
    role = data.get('role', 'pilot')
    orchestrator = SelfCorrectingOrchestrator(user_role=role)
    return JSONResponse(content={'status': 'success', 'role': role})

@app.get("/get_stats")
async def get_stats():
    manager = BattlefieldGraphManager()
    return JSONResponse(content=manager.get_statistics())

@app.get("/api/graph")
async def get_graph():
    manager = BattlefieldGraphManager()
    nodes = []
    links = []
    if manager._use_fallback:
        for node_id, attrs in manager.fallback_graph.nodes(data=True):
            nodes.append({
                'id': node_id,
                'type': attrs.get('entity_type', 'Unknown'),
                'name': attrs.get('name', node_id),
                'properties': attrs
            })
        for source, target, attrs in manager.fallback_graph.edges(data=True):
            links.append({'source': source, 'target': target})
    return JSONResponse(content={'nodes': nodes, 'links': links})

@app.get("/api/ontology")
async def get_ontology():
    manager = BattlefieldGraphManager()
    entities = []
    if manager._use_fallback:
        for node_id, attrs in manager.fallback_graph.nodes(data=True):
            entities.append({'id': node_id, 'type': attrs.get('entity_type', 'Unknown'), 'properties': attrs})
    return JSONResponse(content={'entities': entities, 'stats': manager.get_statistics()})

if __name__ == '__main__':
    import uvicorn
    print("🌐 启动网页界面: http://localhost:5000")
    uvicorn.run(app, host='0.0.0.0', port=5000)
