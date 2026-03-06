"""Admin UI routes"""

import logging
import os
from fastapi import APIRouter, Request, Depends, HTTPException, status, Header
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import HTMLResponse
from pathlib import Path
from typing import Optional

from .router import router
from .config import settings
from . import database

logger = logging.getLogger(__name__)

admin_router = APIRouter(prefix="/admin", tags=["admin"])
security = HTTPBasic()


async def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)) -> dict:
    """验证用户名密码 - 支持多用户"""
    user = await database.get_user_by_credentials(credentials.username, credentials.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    if not user.get("enabled"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User disabled",
        )
    
    return user


# HTML Templates
ADMIN_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenClaw Relay 管理</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
               background: #f5f5f5; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { color: #333; margin-bottom: 20px; }
        
        .card { background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        
        .instance-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }
        
        .instance { border: 1px solid #e0e0e0; border-radius: 8px; padding: 16px; }
        .instance h3 { margin-bottom: 8px; color: #333; }
        .instance .url { color: #666; font-size: 14px; margin-bottom: 12px; }
        
        .status { display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 12px; }
        .status.online { background: #d4edda; color: #155724; }
        .status.offline { background: #f8d7da; color: #721c24; }
        .status.unknown { background: #fff3cd; color: #856404; }
        
        .form-group { margin-bottom: 16px; }
        label { display: block; margin-bottom: 4px; font-weight: 500; color: #333; }
        input, select { width: 100%; padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px; }
        
        .btn { padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }
        .btn-primary { background: #007bff; color: white; }
        .btn-success { background: #28a745; color: white; }
        .btn-danger { background: #dc3545; color: white; }
        
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f8f9fa; font-weight: 600; }
        
        /* 统一导航 */
        .nav { background: #2c3e50; padding: 12px 20px; border-radius: 8px; margin-bottom: 20px; }
        .nav h1 { color: white; margin: 0; display: inline-block; font-size: 20px; }
        .nav-links { float: right; }
        .nav-links a { color: white; text-decoration: none; margin-left: 12px; padding: 8px 16px; border-radius: 4px; }
        .nav-links a:hover { background: #34495e; }
        .nav-links a.active { background: #3498db; }
    </style>
</head>
<body>
        <!-- 统一导航栏 -->
        <div class="nav" style="background: #2c3e50; padding: 12px 20px; border-radius: 8px; margin-bottom: 20px;">
            <h1 style="color: white; margin: 0; display: inline-block; font-size: 20px;">🚀 Henjiu Relay</h1>
            <div style="float: right;">
                <a href="/admin/dashboard" style="color: white; text-decoration: none; margin-left: 12px; padding: 8px 16px; border-radius: 4px;">📊 监控台</a>
                <a href="/admin/users" style="color: white; text-decoration: none; margin-left: 12px; padding: 8px 16px; border-radius: 4px;">👥 用户</a>
                <a href="/admin" style="color: white; text-decoration: none; margin-left: 12px; padding: 8px 16px; border-radius: 4px;">🖥️ 实例</a>
                <a href="/admin/api-docs" style="color: white; text-decoration: none; margin-left: 12px; padding: 8px 16px; border-radius: 4px;">📚 API</a>
            </div>
        </div>

    <div class="container">
        <div class="card">
            <h2>实例列表</h2>
            <div style="margin: 16px 0;">
                <button class="btn btn-success" onclick="showAddForm()">+ 添加实例</button>
                <button class="btn btn-primary" onclick="checkAllStatus()">🔄 检查全部状态</button>
            </div>
            
            <div id="addForm" style="display:none; background:#f8f9fa; padding:16px; border-radius:8px; margin-bottom:16px;">
                <h3>添加新实例</h3>
                <div class="form-group">
                    <label>ID (唯一标识)</label>
                    <input type="text" id="newId" placeholder="例如: tianyi">
                </div>
                <div class="form-group">
                    <label>名称</label>
                    <input type="text" id="newName" placeholder="例如: 天翼云-冯麟">
                </div>
                <div class="form-group">
                    <label>URL (OpenClaw 地址)</label>
                    <input type="text" id="newUrl" placeholder="http://192.168.1.10:18789">
                </div>
                <div class="form-group">
                    <label>连接 Token (自动生成)</label>
                    <input type="text" id="newAuthToken" placeholder="点击随机生成">
                    <button type="button" class="btn" onclick="document.getElementById('newAuthToken').value=Math.random().toString(36).substr(2,16)">🎲 随机生成</button>
                </div>
                <button class="btn btn-success" onclick="addInstance()">保存</button>
                <button class="btn" onclick="hideAddForm()">取消</button>
            </div>
            
            <div id="editForm" style="display:none; background:#fff3cd; padding:16px; border-radius:8px; margin-bottom:16px;">
                <h3>编辑实例</h3>
                <input type="hidden" id="editId">
                <div class="form-group">
                    <label>名称</label>
                    <input type="text" id="editName" placeholder="实例名称">
                </div>
                <div class="form-group">
                    <label>URL</label>
                    <input type="text" id="editUrl" placeholder="http://192.168.1.10:18789">
                </div>
                <div class="form-group">
                    <label>Token</label>
                    <input type="text" id="editToken" placeholder="连接Token">
                </div>
                <button class="btn btn-success" onclick="saveEdit()">保存</button>
                <button class="btn" onclick="hideEditForm()">取消</button>
            </div>
            
            <div class="instance-grid" id="instances"></div>
        </div>
        
        <div class="card">
            <h2>API 文档</h2>
            <table>
                <tr><th>端点</th><th>方法</th><th>说明</th></tr>
                <tr><td>/health</td><td>GET</td><td>健康检查</td></tr>
                <tr><td>/api/send</td><td>POST</td><td>发送消息</td></tr>
                <tr><td>/api/instances</td><td>GET</td><td>列出实例</td></tr>
                <tr><td>/api/instances/{id}</td><td>GET</td><td>获取实例</td></tr>
                <tr><td>/api/sessions</td><td>GET</td><td>列出所有会话</td></tr>
                <tr><td>/api/reload</td><td>POST</td><td>重载配置</td></tr>
            </table>
        </div>
    </div>
    
    <script>
        let instances = [];
        
        async function loadInstances() {
            try {
                const headers = new Headers({});
                // 检查 URL 是否已包含认证信息
                if (!window.location.href.includes('@')) {
                    headers.append('Authorization', 'Basic ' + btoa('admin:123456'));
                }
                const resp = await fetch('/api/instances', { headers });
                if (!resp.ok) {
                    console.log('加载失败:', resp.status);
                    return;
                }
                const data = await resp.json();
                if (data.instances && data.instances.length > 0) {
                    instances = data.instances;
                    render();
                }
            } catch(e) {
                console.log('加载错误:', e);
            }
        }
        
        function render() {
            const container = document.getElementById('instances');
            container.innerHTML = instances.map(inst => `
                <div class="instance">
                    <h3>${inst.name || inst.id} <span class="status ${inst.online ? 'status-online' : 'status-offline'}">${inst.online ? '在线' : '离线'}</span></h3>
                    <div class="url">${inst.url}</div>
                    <div style="margin-top:8px;">
                        <button class="btn btn-primary" onclick="checkStatus('${inst.id}')">检查</button>
                        <button class="btn btn-warning" onclick="editInstance('${inst.id}')">编辑</button>
                        <button class="btn btn-danger" onclick="deleteInstance('${inst.id}')">删除</button>
                    </div>
                </div>
            `).join('');
        }
        
        async function checkStatus(id) {
            try {
                const headers = new Headers({});
                if (!window.location.href.includes('@')) {
                    headers.append('Authorization', 'Basic ' + btoa('admin:123456'));
                }
                const resp = await fetch('/api/instances/' + id + '/status', { headers });
                const data = await resp.json();
                alert(id + ': ' + (data.online ? '在线' : '离线'));
                loadInstances();
            } catch(e) {
                alert('检查失败: ' + e);
            }
        }
        
        async function checkAllStatus() {
            for (const inst of instances) {
                await checkStatus(inst.id);
            }
        }
        
        async function deleteInstance(id) {
            if (!confirm('确定删除 ' + id + '?')) return;
            if (!confirm('再次确认：彻底删除实例 ' + id + '？此操作不可恢复！')) return;
            alert('删除功能开发中');
        }
        
        function editInstance(id) {
            const inst = instances.find(i => i.id === id);
            if (!inst) return;
            document.getElementById('editId').value = id;
            document.getElementById('editName').value = inst.name || '';
            document.getElementById('editUrl').value = inst.url || '';
            document.getElementById('editToken').value = inst.auth_token || '';
            document.getElementById('editForm').style.display = 'block';
            document.getElementById('addForm').style.display = 'none';
        }
        
        function hideEditForm() {
            document.getElementById('editForm').style.display = 'none';
        }
        
        async function saveEdit() {
            const id = document.getElementById('editId').value;
            const name = document.getElementById('editName').value;
            const url = document.getElementById('editUrl').value;
            const auth_token = document.getElementById('editToken').value;
            
            const headers = new Headers({
                'Content-Type': 'application/json'
            });
            if (!window.location.href.includes('@')) {
                headers.append('Authorization', 'Basic ' + btoa('admin:123456'));
            }
            
            const body = {};
            if (name) body.name = name;
            if (url) body.url = url;
            if (auth_token) body.auth_token = auth_token;
            
            try {
                const resp = await fetch('/api/instances/' + id, {
                    method: 'PUT',
                    headers,
                    body: JSON.stringify(body)
                });
                const data = await resp.json();
                if (data.success) {
                    alert('保存成功');
                    hideEditForm();
                    loadInstances();
                } else {
                    alert('保存失败: ' + data.error);
                }
            } catch(e) {
                alert('保存失败: ' + e);
            }
        }
        
        function showAddForm() {
            document.getElementById('addForm').style.display = 'block';
        }
        
        function hideAddForm() {
            document.getElementById('addForm').style.display = 'none';
        }
        
        async function addInstance() {
            const id = document.getElementById('newId').value;
            const name = document.getElementById('newName').value;
            const url = document.getElementById('newUrl').value;
            const authToken = document.getElementById('newAuthToken').value || Math.random().toString(36).substr(2,16);
            
            // 生成随机 Token
            if (!document.getElementById('newAuthToken').value) {
                document.getElementById('newAuthToken').value = authToken;
            }
            
            // TODO: 保存到服务器
            alert('保存功能开发中，请先手动配置 .env 文件');
            hideAddForm();
        }
        
        loadInstances();
    </script>
</body>
</html>
"""

DASHBOARD_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenClaw Relay 状态</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
               background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        
        h1 { color: white; text-align: center; margin-bottom: 30px; font-size: 2.5em; }
        
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: white; border-radius: 12px; padding: 24px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .stat-number { font-size: 3em; font-weight: bold; color: #667eea; }
        .stat-label { color: #666; margin-top: 8px; }
        
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 20px; }
        
        .instance-card { background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .instance-header { padding: 20px; background: #f8f9fa; display: flex; justify-content: space-between; align-items: center; }
        .instance-name { font-size: 1.25em; font-weight: 600; color: #333; }
        .status-badge { padding: 6px 16px; border-radius: 20px; font-weight: 500; font-size: 14px; }
        .status-online { background: #d4edda; color: #155724; }
        .status-offline { background: #f8d7da; color: #721c24; }
        .status-checking { background: #fff3cd; color: #856404; }
        
        .instance-body { padding: 20px; }
        .info-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #eee; }
        .info-label { color: #666; }
        .info-value { color: #333; font-weight: 500; }
        
        .instance-footer { padding: 16px 20px; background: #f8f9fa; display: flex; gap: 10px; }
        .btn { padding: 8px 16px; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; text-decoration: none; }
        .btn-primary { background: #667eea; color: white; }
        .btn-outline { background: white; border: 1px solid #667eea; color: #667eea; }
        
        .footer { text-align: center; color: rgba(255,255,255,0.7); margin-top: 40px; }
    </style>
</head>
<body>
        <!-- 统一导航栏 -->
        <div class="nav" style="background: #2c3e50; padding: 12px 20px; border-radius: 8px; margin-bottom: 20px;">
            <h1 style="color: white; margin: 0; display: inline-block; font-size: 20px;">🚀 Henjiu Relay</h1>
            <div style="float: right;">
                <a href="/admin/dashboard" style="color: white; text-decoration: none; margin-left: 12px; padding: 8px 16px; border-radius: 4px;">📊 监控台</a>
                <a href="/admin/users" style="color: white; text-decoration: none; margin-left: 12px; padding: 8px 16px; border-radius: 4px;">👥 用户</a>
                <a href="/admin" style="color: white; text-decoration: none; margin-left: 12px; padding: 8px 16px; border-radius: 4px;">🖥️ 实例</a>
                <a href="/admin/api-docs" style="color: white; text-decoration: none; margin-left: 12px; padding: 8px 16px; border-radius: 4px;">📚 API</a>
            </div>
        </div>

        <h1>📊 监控台</h1>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-number" id="totalInstances">-</div>
                <div class="stat-label">实例总数</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="onlineInstances">-</div>
                <div class="stat-label">在线</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="offlineInstances">-</div>
                <div class="stat-label">离线</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="totalSessions">-</div>
                <div class="stat-label">活动会话</div>
            </div>
        </div>
        
        <div class="grid" id="instances"></div>
        
        <div class="footer">
            <p>OpenClaw Relay v0.2.0 | <a href="/admin" style="color: white;">管理界面</a></p>
        </div>
    </div>
    
    <script>
        let instances = [];
        
        async function loadData() {
            await Promise.all([loadInstances(), loadSessions()]);
            renderInstances();
            updateStats();
        }
        
        async function checkInstanceStatus(instanceId) {
            try {
                const headers = new Headers({});
                if (!window.location.href.includes('@')) {
                    headers.append('Authorization', 'Basic ' + btoa('admin:123456'));
                }
                const resp = await fetch('/api/instances/' + instanceId + '/status', { headers });
                const data = await resp.json();
                alert(instanceId + ': ' + (data.online ? '在线' : '离线'));
            } catch(e) {
                alert('检查失败: ' + e);
            }
        }
        
        async function viewInstanceSessions(instanceId) {
            try {
                const headers = new Headers({});
                if (!window.location.href.includes('@')) {
                    headers.append('Authorization', 'Basic ' + btoa('admin:123456'));
                }
                const resp = await fetch('/api/sessions?instance_id=' + instanceId, { headers });
                const data = await resp.json();
                const sessions = data[instanceId] || [];
                if (sessions.length === 0) {
                    alert('暂无活动会话');
                } else {
                    const sessionInfo = sessions.map(s => s.key || s.id || s.session_key).join('\\n');
                    alert('活动会话 (' + sessions.length + '):\\n' + sessionInfo);
                }
            } catch(e) {
                alert('获取会话失败: ' + e);
            }
        }
        
        async function loadInstances() {
            try {
                const headers = new Headers({});
                if (!window.location.href.includes('@')) {
                    headers.append('Authorization', 'Basic ' + btoa('admin:123456'));
                }
                const resp = await fetch('/api/instances', { headers });
                const data = await resp.json();
                instances = data.instances || [];
            } catch(e) {
                console.error(e);
            }
        }
        
        let sessionsData = {};
        async function loadSessions() {
            try {
                const headers = new Headers({});
                if (!window.location.href.includes('@')) {
                    headers.append('Authorization', 'Basic ' + btoa('admin:123456'));
                }
                const resp = await fetch('/api/sessions', { headers });
                sessionsData = await resp.json();
            } catch(e) {
                console.error(e);
            }
        }
        
        function renderInstances() {
            const container = document.getElementById('instances');
            container.innerHTML = instances.map(inst => {
                const sessions = sessionsData[inst.id] || [];
                const sessionCount = Array.isArray(sessions) ? sessions.length : 0;
                const isOnline = inst.online === true;
                const statusClass = isOnline ? 'status-online' : 'status-offline';
                const statusText = isOnline ? '🟢 在线' : '🔴 离线';
                
                return `
                <div class="instance-card">
                    <div class="instance-header">
                        <div class="instance-name">${inst.name || inst.id}</div>
                        <div class="status-badge ${statusClass}">${statusText}</div>
                    </div>
                    <div class="instance-body">
                        <div class="info-row">
                            <span class="info-label">URL</span>
                            <span class="info-value">${inst.url}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">认证</span>
                            <span class="info-value">${inst.auth_token || '-'}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">会话数</span>
                            <span class="info-value">${sessionCount}</span>
                        </div>
                    </div>
                    <div class="instance-footer">
                        <button class="btn btn-outline" onclick="checkInstanceStatus('${inst.id}')">🔄 检查</button>
                        <button class="btn btn-primary" onclick="viewInstanceSessions('${inst.id}')">📋 会话</button>
                    </div>
                </div>
                `;
            }).join('');
        }
        
        function updateStats() {
            document.getElementById('totalInstances').textContent = instances.length;
            document.getElementById('onlineInstances').textContent = instances.filter(i => i.online === true).length;
            document.getElementById('offlineInstances').textContent = instances.filter(i => i.online === false).length;
            
            let totalSessions = 0;
            for (const sid in sessionsData) {
                if (Array.isArray(sessionsData[sid])) {
                    totalSessions += sessionsData[sid].length;
                }
            }
            document.getElementById('totalSessions').textContent = totalSessions;
        }
        
        // Auto refresh every 30s
        loadData();
        setInterval(loadData, 30000);
    </script>
</body>
</html>
"""


@admin_router.get("/", response_class=HTMLResponse)
async def admin_page(current_user: dict = Depends(verify_credentials)):
    """管理页面 - 服务端渲染"""
    from .websocket import ws_server
    connected_ids = set(ws_server.connections.keys())
    from .router import router
    instances = router.list_instances()
    
    # 构建实例 HTML
    instances_html = ""
    for inst in instances:
        inst_id = inst.get("id", "")
        is_online = inst_id in connected_ids
        status_class = "status-online" if is_online else "status-offline"
        status_text = "在线" if is_online else "离线"
        
        instances_html += f"""
        <div class="instance">
            <h3>{inst.get('name', inst.get('id', 'Unknown'))}</h3>
            <p class="url">{inst.get('url', '-')}</p>
            <span class="status {status_class}">{status_text}</span>
        </div>
        """
    
    if not instances_html:
        instances_html = '<p>暂无实例，请添加</p>'
    
    # 替换
    page = ADMIN_PAGE
    page = page.replace('id="instances"></div>', f'id="instances">{instances_html}</div>')
    
    return page


@admin_router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(current_user: dict = Depends(verify_credentials)):
    """监控台页面"""
    # 获取实例数据 - 从配置读取
    from .config import settings
    
    # 获取连接的实例
    from .websocket import ws_server
    connected_ids = set(ws_server.connections.keys())
    
    # 构建实例卡片 HTML
    instances_html = ""
    online_count = 0
    
    # 从配置读取实例
    instances = []
    if hasattr(settings, 'instances'):
        for inst in settings.instances:
            inst_dict = {
                "id": inst.id if hasattr(inst, 'id') else inst.get('id'),
                "name": inst.name if hasattr(inst, 'name') else inst.get('name'),
                "url": inst.url if hasattr(inst, 'url') else inst.get('url'),
                "auth_token": inst.auth_token if hasattr(inst, 'auth_token') and inst.auth_token else (inst.auth.token if hasattr(inst, 'auth') and inst.auth and hasattr(inst.auth, 'token') else '')
            }
            instances.append(inst_dict)
    
    for inst in instances:
        inst_id = inst.get("id", "")
        is_online = inst_id in connected_ids
        if is_online:
            online_count += 1
        
        status_class = "status-online" if is_online else "status-offline"
        status_text = "在线" if is_online else "离线"
        
        instances_html += f"""
        <div class="instance-card">
            <div class="instance-header">
                <span class="instance-name">{inst.get('name', inst.get('id', 'Unknown'))}</span>
                <span class="status-badge {status_class}">{status_text}</span>
            </div>
            <div class="instance-body">
                <div class="info-row">
                    <span class="info-label">ID</span>
                    <span class="info-value">{inst.get('id', '-')}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">URL</span>
                    <span class="info-value">{inst.get('url', '-')}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">类型</span>
                    <span class="info-value">${inst.get('auth_token', '-')}</span>
                </div>
            </div>
        </div>
        """
    
    if not instances_html:
        instances_html = '<p style="color:white;text-align:center;">暂无实例</p>'
    
    # 替换模板中的变量
    page = DASHBOARD_PAGE
    page = page.replace('"totalInstances">-"', f'"totalInstances">{len(instances)}"')
    page = page.replace('"onlineInstances">-"', f'"onlineInstances">{online_count}"')
    page = page.replace('"offlineInstances">-"', f'"offlineInstances">{len(instances) - online_count}"')
    page = page.replace('id="instances"></div>', f'id="instances">{instances_html}</div>')
    
    return page


# API Docs Page
API_DOCS_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenClaw Relay API 手册</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
               background: #f5f5f5; padding: 20px; }
        .container { max-width: 1000px; margin: 0 auto; }
        h1 { color: #333; margin-bottom: 20px; }
        h2 { color: #555; margin: 24px 0 12px; border-bottom: 2px solid #667eea; padding-bottom: 8px; }
        
        .card { background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        
        .endpoint { background: #f8f9fa; border-radius: 6px; padding: 16px; margin-bottom: 16px; }
        .method { display: inline-block; padding: 4px 12px; border-radius: 4px; font-weight: bold; font-size: 14px; margin-right: 12px; }
        .method.get { background: #61affe; color: white; }
        .method.post { background: #49cc90; color: white; }
        .method.put { background: #fca130; color: white; }
        .method.delete { background: #f93e3e; color: white; }
        
        .path { font-family: monospace; font-size: 16px; color: #333; }
        
        .description { color: #666; margin: 8px 0; }
        
        .params { margin-top: 12px; }
        .param { background: white; padding: 8px 12px; border-left: 3px solid #667eea; margin-bottom: 8px; }
        .param-name { font-weight: bold; color: #333; }
        .param-type { color: #999; font-size: 12px; }
        .param-required { color: #f93e3e; font-size: 12px; }
        
        pre { background: #282c34; color: #abb2bf; padding: 16px; border-radius: 6px; overflow-x: auto; }
        code { font-family: 'Monaco', 'Menlo', monospace; }
        
        .example-response { margin-top: 12px; }
        
        .nav { background: white; padding: 12px 20px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .nav a { color: #667eea; text-decoration: none; margin-right: 20px; }
        .nav a:hover { text-decoration: underline; }
    </style>
</head>
<body>
        <!-- 统一导航栏 -->
        <div class="nav" style="background: #2c3e50; padding: 12px 20px; border-radius: 8px; margin-bottom: 20px;">
            <h1 style="color: white; margin: 0; display: inline-block; font-size: 20px;">🚀 Henjiu Relay</h1>
            <div style="float: right;">
                <a href="/admin/dashboard" style="color: white; text-decoration: none; margin-left: 12px; padding: 8px 16px; border-radius: 4px;">📊 监控台</a>
                <a href="/admin/users" style="color: white; text-decoration: none; margin-left: 12px; padding: 8px 16px; border-radius: 4px;">👥 用户</a>
                <a href="/admin" style="color: white; text-decoration: none; margin-left: 12px; padding: 8px 16px; border-radius: 4px;">🖥️ 实例</a>
                <a href="/admin/api-docs" style="color: white; text-decoration: none; margin-left: 12px; padding: 8px 16px; border-radius: 4px;">📚 API</a>
            </div>
        </div>

    <div class="container">
        <h1>📚 OpenClaw Relay API 手册</h1>
        
        <div class="card">
            <h2>概述</h2>
            <p>OpenClaw Relay 提供 HTTP API 用于消息转发和实例管理。</p>
            <p style="margin-top:12px;"><strong>基础地址:</strong> <code>http://your-server:8080</code></p>
        </div>
        
        <div class="card">
            <h2>认证说明</h2>
            <p>所有 API 接口都需要认证：</p>
            
            <h3>方式1: API Key (推荐)</h3>
            <pre><code># 在 Header 中添加 X-API-Key

# 获取 API Key (需要管理员账号)
# 登录管理后台 → 用户 → 查看或重置

# cURL
curl -H "X-API-Key: your-api-key" http://localhost:8080/api/send

# Python
headers = {"X-API-Key": "your-api-key"}
requests.post('http://localhost:8080/api/send', json={...}, headers=headers)

# JavaScript
fetch('http://localhost:8080/api/send', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': 'your-api-key'
  },
  body: JSON.stringify({
    message: "Hello",
    instance_id: "cc2-openclaw",  // 必填
    target: "user123"              // 可选
  })
})</code></pre>
            
            <h3>方式2: 管理员 Basic Auth</h3>
            <pre><code># 管理员可以使用用户名密码

# cURL
curl -u admin:password http://localhost:8080/api/users

# Python
requests.get('http://localhost:8080/api/users', auth=('admin', 'password'))</code></pre>
        </div>
        
        <div class="card">
            <h2>唯一无需认证的接口</h2>
            <pre><code>/health - 服务健康检查</code></pre>
        </div>
        
        <div class="card">
            <div class="endpoint">
                <span class="method get">GET</span>
                <span class="path">/health</span>
                <p class="description">服务健康检查</p>
                <div class="params">
                    <div class="param"><span class="param-name">返回值</span> <span class="param-type">JSON</span></div>
                </div>
                <pre><code>{
  "status": "ok",
  "channel": "relay",
  "http_port": 8080,
  "ws_port": 8081
}</code></pre>
            </div>
        </div>
        
        <h2>消息接口</h2>
        <p style="color:#dc3545;margin-bottom:12px;">🔐 需要 API Key 认证 (Header: X-API-Key)</p>
        
        <div class="card">
            <div class="endpoint">
                <span class="method post">POST</span>
                <span class="path">/api/send</span>
                <p class="description">发送消息到指定的 OpenClaw 实例（通过 WebSocket）</p>
                <div class="params">
                    <div class="param"><span class="param-name">message</span> <span class="param-type">string</span> <span class="param-required">必填</span> 消息内容</div>
                    <div class="param"><span class="param-name">instance_id</span> <span class="param-type">string</span> <span class="param-required">必填</span> 目标实例ID</div>
                    <div class="param"><span class="param-name">target</span> <span class="param-type">string</span> 目标用户/聊天ID</div>
                    <div class="param"><span class="param-name">sender_id</span> <span class="param-type">string</span> 发送者ID</div>
                    <div class="param"><span class="param-name">metadata</span> <span class="param-type">object</span> 额外元数据</div>
                </div>
                <pre><code># 请求
curl -X POST http://localhost:8080/api/send \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: your-api-key" \\
  -d '{"message": "Hello", "instance_id": "cc2-openclaw"}'

# 响应
{
  "success": true,
  "message_id": "ws-cc2-openclaw-xxx",
  "instance_id": "cc2-openclaw",
  "reply": null  // OpenClaw 的回复（如果有）
}</code></pre>
            </div>
        </div>
        
        <h2>实例管理</h2>
        
        <div class="card">
            <div class="endpoint">
                <span class="method get">GET</span>
                <span class="path">/api/instances</span>
                <p class="description">列出所有配置的实例</p>
                <pre><code>{
  "instances": [
    {"id": "a", "name": "Claw A", "url": "http://192.168.1.10:18789", "enabled": true},
    {"id": "b", "name": "Claw B", "url": "http://192.168.1.11:18789", "enabled": true}
  ],
  "default": "a"
}</code></pre>
            </div>
            
            <div class="endpoint">
                <span class="method get">GET</span>
                <span class="path">/api/instances/{instance_id}</span>
                <p class="description">获取指定实例信息</p>
                <pre><code>{
  "id": "a",
  "name": "Claw A", 
  "url": "http://192.168.1.10:18789",
  "enabled": true
}</code></pre>
            </div>
            
            <div class="endpoint">
                <span class="method get">GET</span>
                <span class="path">/api/instances/{instance_id}/status</span>
                <p class="description">检查实例连通性</p>
                <pre><code>{
  "id": "a",
  "name": "Claw A",
  "url": "http://192.168.1.10:18789", 
  "online": true,
  "response": {"status": "ok"}
}</code></pre>
            </div>
        </div>
        
        <h2>会话管理</h2>
        
        <div class="card">
            <div class="endpoint">
                <span class="method get">GET</span>
                <span class="path">/api/sessions</span>
                <p class="description">列出所有实例的活动会话</p>
                <div class="params">
                    <div class="param"><span class="param-name">instance_id</span> <span class="param-type">string</span> 可选，指定实例</div>
                </div>
                <pre><code>{
  "a": [{"key": "agent:main", "kind": "direct", "updatedAt": 1234567890}],
  "b": [{"key": "agent:main", "kind": "group", "updatedAt": 1234567890}]
}</code></pre>
            </div>
        </div>
        
        <h2>配置管理</h2>
        
        <div class="card">
            <div class="endpoint">
                <span class="method post">POST</span>
                <span class="path">/api/reload</span>
                <p class="description">重新加载配置（从环境变量）</p>
                <pre><code>{"success": true, "message": "Config reloaded"}</code></pre>
            </div>
        </div>
        
        <h2>错误响应</h2>
        
        <div class="card">
            <pre><code># 错误格式
{
  "success": false,
  "error": "Error message"
}

# HTTP 状态码
200 - 成功
401 - 未授权
404 - 资源不存在
500 - 服务器错误</code></pre>
        </div>
        
        <h2>🚀 远程插件部署指南</h2>
        
        <div class="card">
            <h3>项目结构</h3>
            <p>Henjiu Relay 包含两个项目：</p>
            <ul>
                <li><strong>服务端</strong> - 你当前访问的 (henjiu-relay-server)</li>
                <li><strong>插件</strong> - 安装到远程 OpenClaw (henjiu-relay)</li>
            </ul>
        </div>
        
        <div class="card">
            <h3>步骤 1: 复制插件到远程服务器</h3>
            <p>将 <code>henjiu-relay/</code> 目录复制到远程服务器的 <code>~/.openclaw/extensions/relay/</code></p>
            <pre><code># 在远程服务器执行
mkdir -p ~/.openclaw/extensions/relay

# 复制文件 (通过 scp 或其他方式)
# 需要的文件:
# - index.js
# - package.json
# - relay-plugin.json</code></pre>
        </div>
        
        <div class="card">
            <h3>步骤 2: 安装依赖</h3>
            <pre><code>cd ~/.openclaw/extensions/relay
npm install ws</code></pre>
        </div>
        
        <div class="card">
            <h3>步骤 3: 配置 OpenClaw</h3>
            <pre><code>openclaw config.patch '{
  "channels": {
    "relay": {
      "enabled": true,
      "relayUrl": "ws://你的服务端IP:8081",
      "instanceId": "tianyi",
      "instanceName": "天翼云-冯麟",
      "authToken": "tianyi-token-2024"
    }
  },
  "plugins": {
    "allow": ["relay"]
  }
}'</code></pre>
            <p style="color:#dc3545;"><strong>⚠️ 重要: authToken 必须与服务端配置的实例 auth_token 一致!</strong></p>
            <p><strong>配置说明：</strong></p>
            <table>
                <tr><th>配置项</th><th>说明</th><th>示例</th></tr>
                <tr><td>relayUrl</td><td>服务端 WebSocket 地址</td><td>ws://192.168.111.201:8081</td></tr>
                <tr><td>instanceId</td><td>唯一标识，必须与服务端一致</td><td>tianyi</td></tr>
                <tr><td>instanceName</td><td>显示名称</td><td>天翼云-冯麟</td></tr>
                <tr><td>authToken</td><td>连接认证 Token，必须与服务端 auth_token 一致</td><td>tianyi-token-2024</td></tr>
            </table>
        </div>
        
        <div class="card">
            <h3>步骤 4: 重启 OpenClaw</h3>
            <pre><code>openclaw gateway restart</code></pre>
        </div>
        
        <div class="card">
            <h3>步骤 5: 验证连接</h3>
            <p>刷新监控台 http://你的服务端IP:8080/admin/dashboard</p>
            <p>在"已连接的实例"中应该能看到你的实例显示"在线"</p>
            <p>或查看日志：</p>
            <pre><code>openclaw logs | grep -i relay</code></pre>
            <p>应该看到类似输出：</p>
            <pre><code>Relay channel: connecting to ws://192.168.1.100:8081 as tianyi
Relay channel: connected to ws://192.168.1.100:8081
Relay channel: registered as tianyi</code></pre>
        </div>
        
        <div class="card">
            <h3>故障排查</h3>
            
            <h4>连接失败</h4>
            <pre><code># 检查网络
ping 你的服务端IP

# 检查端口
telnet 你的服务端IP 8081</code></pre>
            
            <h4>插件未加载</h4>
            <pre><code># 检查插件允许列表
openclaw config.get plugins.allow</code></pre>
            
            <h4>查看详细日志</h4>
            <pre><code>openclaw logs --follow</code></pre>
        </div>
        
        <div class="card">
            <h3>配置示例</h3>
            <pre><code># 完整配置示例
openclaw config.patch '{
  "channels": {
    "relay": {
      "enabled": true,
      "relayUrl": "ws://192.168.111.201:8081",
      "instanceId": "tianyi",
      "instanceName": "天翼云Windows-冯麟"
    }
  },
  "plugins": {
    "allow": ["relay"]
  }
}'</code></pre>
        </div>
        
        <h2>📐 架构图</h2>
        
        <div class="card">
            <h3>完整调用链路</h3>
            <pre><code>上游应用                    Henjiu Relay                  远程 OpenClaw
    │                              │                                  │
    │  1. HTTP POST               │                                  │
    │  /api/send                  │                                  │
    │────────────────────────────>│                                  │
    │                              │  2. WebSocket 转发              │
    │                              │─────────────────────────────────>│
    │                              │                                  │
    │                              │          3. 本地执行             │
    │                              │     (openclaw agent 处理)        │
    │                              │                                  │
    │                              │  4. WebSocket 响应              │
    │                              │<─────────────────────────────────│
    │                              │                                  │
    │  5. HTTP 响应               │                                  │
    │<────────────────────────────│                                  │</code></pre>
        </div>
        
        <div class="card">
            <h3>部署拓扑</h3>
            <pre><code>┌─────────────────────────────────────────────────────────────┐
│                    你的机房 / 你的电脑                         │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │              Henjiu Relay Server                    │   │
│   │   HTTP :8080  │  WebSocket :8081  │  Admin UI     │   │
│   └──────────────────────┬────────────────────────────────┘   │
└──────────────────────────┼────────────────────────────────────┘
                           │ WebSocket (需网络可达)
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
     ┌─────────┐    ┌─────────┐    ┌─────────┐
     │ 服务器 1 │    │ 服务器 2 │    │ 服务器 N│
     │ OpenClaw│    │ OpenClaw│    │ OpenClaw│
     │  +      │    │  +      │    │  +      │
     │ Plugin  │    │ Plugin  │    │ Plugin  │
     │ Telegram│    │ Feishu  │    │ WhatsApp│
     └─────────┘    └─────────┘    └─────────┘</code></pre>
        </div>
        
        <div class="card">
            <h3>端口与网络</h3>
            <table>
                <tr><th>组件</th><th>端口</th><th>协议</th><th>需要访问</th></tr>
                <tr><td>服务端</td><td>8080</td><td>HTTP</td><td>上游应用</td></tr>
                <tr><td>服务端</td><td>8081</td><td>WebSocket</td><td>远程 OpenClaw</td></tr>
                <tr><td>远程</td><td>18789</td><td>HTTP/WS</td><td>本地访问即可</td></tr>
            </table>
            <p style="margin-top:12px;color:#666;">⚠️ 远程服务器只需要能访问服务端 8081 端口，不需要暴露任何公网端口！</p>
        </div>
        
        <h2>📊 数据流程</h2>
        
        <div class="card">
            <h3>消息发送流程</h3>
            <pre><code>1. 上游 POST /api/send {message, channel}
         │
         ▼
2. Relay 接收请求 → 确定目标实例 (路由匹配)
         │
         ▼
3. WebSocket 转发到对应远程 OpenClaw
         │
         ▼
4. 远程 OpenClaw 通过 Plugin 接收
         │
         ▼
5. injectInbound 注入到 OpenClaw 处理
         │
         ▼
6. Agent 执行 → 生成回复 → 通过 Channel 发送</code></pre>
        </div>
        
        <div class="card">
            <h3>连接管理</h3>
            <pre><code>1. 远程 OpenClaw 发起 WebSocket 连接到服务端 :8081
         │
         ▼
2. 发送注册消息 {type: "register", instance_id, info}
         │
         ▼
3. 服务端确认 {type: "registered", status: "ok"}
         │
         ▼
4. 保持长连接 (心跳每30秒)
         │
         ▼
5. 断开时自动重连 (5秒后)</code></pre>
        </div>
        
        <div class="card">
            <h3>多实例路由规则</h3>
            <pre><code>路由优先级 (按顺序匹配):
1. instance_id (显式指定)
2. channel (通道类型)
3. sender_id (发送者ID)
4. pattern (消息正则匹配)
5. default_instance_id (默认实例)</code></pre>
        </div>
    </div>
</body>
</html>
"""


# Users Management Page
USERS_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>用户管理 - OpenClaw Relay</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
               background: #f5f5f5; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; }
        h1 { color: #333; margin-bottom: 20px; }
        
        .card { background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        
        .btn { padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }
        .btn-primary { background: #007bff; color: white; }
        .btn-success { background: #28a745; color: white; }
        .btn-danger { background: #dc3545; color: white; }
        .btn-warning { background: #ffc107; color: #333; }
        
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f8f9fa; font-weight: 600; }
        
        .form-group { margin-bottom: 16px; }
        label { display: block; margin-bottom: 4px; font-weight: 500; color: #333; }
        input, select { width: 100%; padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px; }
        
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        
        .api-key { 
            font-family: monospace; 
            background: #f8f9fa; 
            padding: 4px 8px; 
            border-radius: 4px;
            font-size: 12px;
        }
        
        .badge { 
            padding: 4px 8px; border-radius: 4px; font-size: 12px; 
        }
        .badge-admin { background: #007bff; color: white; }
        .badge-user { background: #6c757d; color: white; }
        
        .alert { padding: 12px; border-radius: 4px; margin-bottom: 16px; }
        .alert-success { background: #d4edda; color: #155724; }
        .alert-error { background: #f8d7da; color: #721c24; }
        
        /* 统一导航 */
        .nav { background: #2c3e50; padding: 12px 20px; border-radius: 8px; margin-bottom: 20px; }
        .nav h1 { color: white; margin: 0; display: inline-block; font-size: 20px; }
        .nav-links { float: right; }
        .nav-links a { color: white; text-decoration: none; margin-left: 12px; padding: 8px 16px; border-radius: 4px; }
        .nav-links a:hover { background: #34495e; }
        .nav-links a.active { background: #3498db; }
    </style>
</head>
<body>
    <div class="container">
        <!-- 统一导航栏 -->
        <div class="nav" style="background: #2c3e50; padding: 12px 20px; border-radius: 8px; margin-bottom: 20px;">
            <h1 style="color: white; margin: 0; display: inline-block; font-size: 20px;">🚀 Henjiu Relay</h1>
            <div style="float: right;">
                <a href="/admin/dashboard" style="color: white; text-decoration: none; margin-left: 12px; padding: 8px 16px; border-radius: 4px;">📊 监控台</a>
                <a href="/admin/users" style="color: white; text-decoration: none; margin-left: 12px; padding: 8px 16px; border-radius: 4px;">👥 用户</a>
                <a href="/admin" style="color: white; text-decoration: none; margin-left: 12px; padding: 8px 16px; border-radius: 4px;">🖥️ 实例</a>
                <a href="/admin/api-docs" style="color: white; text-decoration: none; margin-left: 12px; padding: 8px 16px; border-radius: 4px;">📚 API</a>
            </div>
        </div>
        
        <div id="message"></div>
        
        <div class="card">
            <h2>添加用户</h2>
            <form method="get">
                <input type="hidden" name="action" value="add">
                <div class="form-group">
                    <label>用户名</label>
                    <input type="text" name="username" placeholder="用户名" required>
                </div>
                <div class="form-group">
                    <label>密码</label>
                    <input type="password" name="password" placeholder="密码" required>
                </div>
                <div class="form-group">
                    <label>角色</label>
                    <select name="role">
                        <option value="user">普通用户</option>
                        <option value="admin">管理员</option>
                    </select>
                </div>
                <button type="submit" class="btn btn-success">添加用户</button>
            </form>
        </div>
        
        <div class="card" style="background: #e8f5e9; border: 2px solid #4caf50;">
            <h3>当前登录用户</h3>
            <p><strong>用户名:</strong> CURRENT_USERNAME</p>
            <p><strong>API Key:</strong> <span class="api-key">CURRENT_USER_API_KEY</span></p>
        </div>
        
        <div class="card">
            <h2>用户列表</h2>
            <table>
                <thead>
                    <tr>
                        <th>用户名</th>
                        <th>API Key</th>
                        <th>角色</th>
                        <th>状态</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody id="usersList">
                    <tr><td colspan="5">加载中...</td></tr>
                </tbody>
            </table>
        </div>
    </div>
    
    <script>
        async function loadUsers() {
            try {
                const resp = await fetch('/api/users');
                const data = await resp.json();
                
                const tbody = document.getElementById('usersList');
                if (data.users && data.users.length > 0) {
                    tbody.innerHTML = data.users.map(u => `
                        <tr>
                            <td>${u.username}</td>
                            <td><span class="api-key">${u.api_key || '(无)'}</span></td>
                            <td><span class="badge badge-${u.role}">${u.role === 'admin' ? '管理员' : '用户'}</span></td>
                            <td>${u.enabled ? '启用' : '禁用'}</td>
                            <td>
                                <button class="btn btn-warning" onclick="regenerateKey('${u.username}')">🔄 重置 Key</button>
                                <button class="btn btn-primary" onclick="changePassword('${u.username}')">✏️ 修改密码</button>
                            </td>
                        </tr>
                    `).join('');
                } else {
                    tbody.innerHTML = '<tr><td colspan="5">暂无用户</td></tr>';
                }
            } catch(e) {
                document.getElementById('usersList').innerHTML = '<tr><td colspan="5">加载失败: ' + e + '</td></tr>';
            }
        }
        
        async function addUser() {
            const username = document.getElementById('newUsername').value;
            const password = document.getElementById('newPassword').value;
            const role = document.getElementById('newRole').value;
            
            if (!username || !password) {
                showMessage('请填写用户名和密码', 'error');
                return;
            }
            
            try {
                const resp = await fetch('/api/users', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-API-Key': 'PAGE_REPLACE_KEY'
                    },
                    body: JSON.stringify({username, password, role})
                });
                const data = await resp.json();
                
                if (data.error) {
                    showMessage(data.error, 'error');
                } else {
                    showMessage('用户添加成功! API Key: ' + data.user.api_key, 'success');
                    loadUsers();
                    document.getElementById('newUsername').value = '';
                    document.getElementById('newPassword').value = '';
                }
            } catch(e) {
                showMessage('添加失败: ' + e, 'error');
            }
        }
        
        async function changePassword(username) {
            const newPassword = prompt("请输入新密码:");
            if (!newPassword) return;
            
            fetch('/api/users/' + username + '/password', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': 'PAGE_REPLACE_KEY'
                },
                body: JSON.stringify({password: newPassword})
            })
            .then(resp => resp.json())
            .then(data => {
                if (data.error) {
                    showMessage(data.error, 'error');
                } else {
                    showMessage('密码已修改', 'success');
                }
            })
            .catch(e => showMessage('修改失败: ' + e, 'error'));
        }
            }
        }
        
        async function deleteUser(username) {
            if (!confirm('确定要删除用户 ' + username + ' 吗?')) return;
            
            try {
                const resp = await fetch('/api/users/' + username, {
                    method: 'DELETE',
                    headers: {'X-API-Key': 'PAGE_REPLACE_KEY'}
                });
                const data = await resp.json();
                
                if (data.error) {
                    showMessage(data.error, 'error');
                } else {
                    showMessage('用户已删除', 'success');
                    loadUsers();
                }
            } catch(e) {
                showMessage('删除失败: ' + e, 'error');
            }
        }
        
        async function regenerateKey(username) {
            // 直接执行，不弹确认框
            fetch('/api/users/' + username + '/regenerate-key', {
                    method: 'POST',
                    headers: {'X-API-Key': 'PAGE_REPLACE_KEY'}
                });
                const data = await resp.json();
                
                if (data.error) {
                    showMessage(data.error, 'error');
                } else {
                    showMessage('API Key 已重置: ' + data.api_key, 'success');
                    loadUsers();
                }
            } catch(e) {
                showMessage('重置失败: ' + e, 'error');
            }
        }
        
        function showMessage(msg, type) {
            const div = document.getElementById('message');
            div.innerHTML = '<div class="alert alert-' + type + '">' + msg + '</div>';
            setTimeout(() => div.innerHTML = '', 5000);
        }
        
        loadUsers();
        console.log('Page loaded, calling loadUsers');
    </script>
</body>
</html>
"""


@admin_router.get("/users", response_class=HTMLResponse)
async def users_page(current_user: dict = Depends(verify_credentials), request: Request = None):
    """用户管理页面"""
    # 获取当前用户的 API Key
    current_key = current_user.get("api_key", "")
    current_username = current_user.get("username", "")
    current_role = current_user.get("role", "user")
    is_admin = current_role == "admin" or current_user.get("is_root", 0) == 1
    
    # 获取所有用户数据 (服务端渲染)
    from . import database
    users = await database.list_users()
    
    # 处理表单操作 (不需要 JavaScript) - 仅管理员可操作
    message = ""
    message_type = "success"
    
    if request and is_admin:
        # 重置 API Key
        if request.query_params.get("action") == "regenerate":
            target_user = request.query_params.get("username")
            if target_user:
                new_key = await database.regenerate_user_api_key(target_user)
                if new_key:
                    message = f"用户 {target_user} 的 API Key 已重置: {new_key}"
                else:
                    message = f"用户 {target_user} 不存在"
                    message_type = "error"
        
        # 修改密码
        elif request.query_params.get("action") == "password":
            target_user = request.query_params.get("username")
            new_password = request.query_params.get("password")
            if target_user and new_password:
                await database.update_user_password(target_user, new_password)
                message = f"用户 {target_user} 的密码已修改"
            else:
                message = "请提供用户名和新密码"
                message_type = "error"
        
        # 添加用户
        elif request.query_params.get("action") == "add":
            new_username = request.query_params.get("username")
            new_password = request.query_params.get("password")
            new_role = request.query_params.get("role", "user")
            if new_username and new_password:
                try:
                    await database.add_user(new_username, new_password, new_role)
                    message = f"用户 {new_username} 添加成功"
                except Exception as e:
                    message = f"添加失败: {str(e)}"
                    message_type = "error"
            else:
                message = "请提供用户名和密码"
                message_type = "error"
        
        # 刷新用户列表
        users = await database.list_users()
    elif request and not is_admin:
        message = "权限不足，只有管理员可操作用户"
        message_type = "error"
    
    # 构建用户列表的 HTML
    users_html = ""
    if users:
        for u in users:
            api_key_display = (u.get("api_key", "")[:8] + "...") if u.get("api_key") else "(无)"
            role_display = "管理员" if u.get("role") == "admin" else "用户"
            enabled_display = "启用" if u.get("enabled") else "禁用"
            
            # 只有管理员可以看到操作按钮
            action_buttons = ""
            if is_admin:
                action_buttons = f"""
                    <a href="?action=regenerate&username={u.get('username', '')}" class="btn btn-warning">🔄 重置 Key</a>
                    <form method="get" style="display:inline;">
                        <input type="hidden" name="action" value="password">
                        <input type="hidden" name="username" value="{u.get('username', '')}">
                        <input type="text" name="password" placeholder="新密码" style="width:80px;">
                        <button type="submit" class="btn btn-primary">✏️</button>
                    </form>
                """
            
            users_html += f"""
                <tr>
                    <td>{u.get("username", "")}</td>
                    <td><span class="api-key">{api_key_display}</span></td>
                    <td><span class="badge badge-{u.get("role", "user")}">{role_display}</span></td>
                    <td>{enabled_display}</td>
                    <td>{action_buttons}</td>
                </tr>
            """
    else:
        users_html = '<tr><td colspan="5">暂无用户</td></tr>'
    
    # 返回页面，注入当前用户信息
    page = USERS_PAGE.replace("CURRENT_USER_API_KEY", current_key).replace("CURRENT_USERNAME", current_username)
    # 替换 "加载中..." 为实际用户数据
    page = page.replace('<td colspan="5">加载中...</td>', users_html)
    # 替换页面中的 fetch，使用当前用户的 API key
    page = page.replace("fetch('/api/users')", "fetch('/api/users', {headers: {'X-API-Key': '" + current_key + "'}})")
    # 替换其他 API 调用中的 PAGE_REPLACE_KEY
    page = page.replace("'X-API-Key': 'PAGE_REPLACE_KEY'", "'X-API-Key': '" + current_key + "'")
    
    # 非管理员隐藏添加用户表单
    if not is_admin:
        page = page.replace('<form method="get">\n                <input type="hidden" name="action" value="add">', '<div style="display:none"><form method="get">\n                <input type="hidden" name="action" value="add">')
        page = page.replace('</form>\n        </div>\n        \n        <div class="card" style="background: #e8f5e9', '</form></div>\n        </div>\n        \n        <div class="card" style="background: #e8f5e9')
    
    # 添加消息提示
    if message:
        page = page.replace('<div id="message"></div>', f'<div id="message"><div class="alert alert-{message_type}">{message}</div></div>')
    
    return page


@admin_router.get("/api-docs", response_class=HTMLResponse)
async def api_docs_page(_: bool = Depends(verify_credentials)):
    """API 文档页面"""
    return API_DOCS_PAGE
