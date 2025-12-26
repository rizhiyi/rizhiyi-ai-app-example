document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('agent-form');
    const queryInput = document.getElementById('query');
    const submitBtn = document.getElementById('submit-btn');
    const stopBtn = document.getElementById('stop-btn');
    const newSessionBtn = document.getElementById('new-session-btn');
    const scrollArea = document.getElementById('chat-scroll-area');
    const chatContainer = document.getElementById('chat-container');
    const welcomeMessage = document.getElementById('welcome-message');
    const sessionList = document.getElementById('session-list');
    const newSessionSidebarBtn = document.getElementById('new-session-sidebar-btn');
    const currentSessionTitle = document.getElementById('current-session-title');
    
    // 模板
    const userMessageTemplate = document.querySelector('.user-message-template');
    const statusContainerTemplate = document.querySelector('.status-container-template');
    const errorContainerTemplate = document.querySelector('.error-container-template');

    // 获取配置
    const config = window.CrewAIConfig || {};
    
    // 会话历史
    let chatHistory = [];
    let currentElements = null; // 当前正在运行的对话相关的 DOM 元素
    const mcpContainer = document.getElementById('mcp-servers-container');
    const mcpLoading = document.getElementById('mcp-loading');
    const toolModal = document.getElementById('tool-modal');
    const modalTitle = document.getElementById('modal-title');
    const modalBody = document.getElementById('modal-body');
    const closeModal = document.getElementById('close-modal');
    
    // 配置 Markdown 解析器
    marked.setOptions({
        highlight: function(code, lang) {
            if (lang && hljs.getLanguage(lang)) {
                return hljs.highlight(code, { language: lang }).value;
            }
            return hljs.highlightAuto(code).value;
        },
        breaks: true,
        gfm: true
    });

    let currentRunId = null;
    let pollInterval = null;
    let lastLogsJson = '';
    let currentSessionId = null;

    // 自动调整输入框高度
    queryInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
    });

    // 创建新会话的通用函数
    async function createNewSession() {
        if (currentRunId && !confirm('当前会话正在运行，确定要开启新会话吗？')) {
            return;
        }

        try {
            const response = await fetch(config.newSessionUrl, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': config.csrfToken
                }
            });
            const data = await response.json();
            
            if (data.status === 'ok') {
                // 清空当前聊天界面
                chatContainer.innerHTML = '';
                chatHistory = [];
                welcomeMessage.style.display = 'block';
                queryInput.value = '';
                queryInput.style.height = 'auto';
                currentSessionId = data.session_id;
                currentSessionTitle.innerText = '新会话';
                
                // 如果正在轮询，停止它
                stopPolling();
                currentRunId = null;
                
                // 刷新会话列表
                await loadSessions();
                
                console.log('New session created:', data.session_id);
            } else {
                alert('创建新会话失败: ' + (data.error || '未知错误'));
            }
        } catch (error) {
            console.error('Failed to create new session:', error);
            alert('创建新会话失败，请重试');
        }
    }

    // 加载会话列表
    async function loadSessions() {
        try {
            const response = await fetch(config.sessionsUrl);
            const data = await response.json();
            
            if (sessionList) {
                sessionList.innerHTML = '';
                if (data.sessions && data.sessions.length > 0) {
                    data.sessions.forEach(session => {
                        const isActive = currentSessionId == session.id;
                        const item = document.createElement('div');
                        item.className = `session-item ${isActive ? 'active' : ''}`;
                        item.dataset.id = session.id;
                        item.innerHTML = `
                            <div style="flex: 1; overflow: hidden;">
                                <div class="session-title" title="${session.title}">${session.title}</div>
                                <div class="session-date">${session.updated_at}</div>
                            </div>
                            <div class="session-delete" title="删除会话" data-id="${session.id}">
                                <i class="fas fa-trash-alt"></i>
                            </div>
                        `;
                        
                        item.addEventListener('click', (e) => {
                            if (e.target.closest('.session-delete')) {
                                deleteSession(session.id);
                            } else {
                                selectSession(session.id);
                            }
                        });
                        
                        sessionList.appendChild(item);
                    });
                } else {
                    sessionList.innerHTML = `
                        <div style="text-align: center; padding: 40px 20px; color: #bfbfbf;">
                            <i class="fas fa-comments" style="font-size: 32px; margin-bottom: 12px; opacity: 0.2;"></i>
                            <p style="font-size: 13px;">暂无历史会话</p>
                        </div>
                    `;
                }
            }
        } catch (error) {
            console.error('Failed to load sessions:', error);
        }
    }

    // 选择会话
    async function selectSession(sessionId) {
        if (currentSessionId == sessionId) return;
        if (currentRunId && !confirm('当前任务正在运行，切换会话将停止查看当前运行状态。确定切换吗？')) {
            return;
        }

        currentSessionId = sessionId;
        
        // 更新 UI 状态
        document.querySelectorAll('.session-item').forEach(item => {
            item.classList.toggle('active', item.dataset.id == sessionId);
        });

        // 停止当前轮询
        stopPolling();
        currentRunId = null;

        // 加载选中会话的历史
        await loadHistory(sessionId);
    }

    // 删除会话
    async function deleteSession(sessionId) {
        if (!confirm('确定要删除这个会话吗？此操作不可撤销。')) {
            return;
        }

        try {
            const response = await fetch(`${config.deleteSessionUrl}${sessionId}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': config.csrfToken
                }
            });
            const data = await response.json();
            
            if (data.status === 'ok') {
                if (currentSessionId == sessionId) {
                    // 如果删除的是当前会话，则加载最新的
                    currentSessionId = null;
                    await loadHistory();
                }
                await loadSessions();
            } else {
                alert('删除失败: ' + (data.error || '未知错误'));
            }
        } catch (error) {
            console.error('Failed to delete session:', error);
            alert('删除失败，请重试');
        }
    }

    // 新会话按钮点击处理
    if (newSessionBtn) {
        newSessionBtn.addEventListener('click', createNewSession);
    }
    if (newSessionSidebarBtn) {
        newSessionSidebarBtn.addEventListener('click', createNewSession);
    }

    // 加载 MCP 服务器信息
    async function loadMCPServers() {
        try {
            const response = await fetch('/oauth/mcp/list/');
            const data = await response.json();
            
            if (mcpLoading) mcpLoading.remove();
            
            data.servers.forEach(server => {
                const item = document.createElement('div');
                item.className = 'feature-item mcp-server';
                item.innerHTML = `
                    <div class="status-dot ${server.connected ? 'status-online' : 'status-offline'}"></div>
                    <h4 style="color: ${server.color};"><i class="fas ${server.icon}"></i> ${server.name}</h4>
                    <p>${server.description}</p>
                `;
                
                item.addEventListener('click', () => showToolDetails(server));
                mcpContainer.appendChild(item);
            });
        } catch (error) {
            console.error('Failed to load MCP servers:', error);
            if (mcpLoading) {
                mcpLoading.innerHTML = `<span style="color: #ff4d4f;"><i class="fas fa-exclamation-triangle"></i> 加载失败</span>`;
            }
        }
    }

    function showToolDetails(server) {
        modalTitle.innerText = `${server.name} - 工具列表`;
        modalBody.innerHTML = '';
        
        if (!server.connected) {
            modalBody.innerHTML = `<div style="text-align: center; color: #ff4d4f; padding: 20px;">
                <i class="fas fa-plug" style="font-size: 32px; margin-bottom: 12px; opacity: 0.2;"></i>
                <p>无法连接到该服务器 ${server.error ? `(${server.error})` : ''}</p>
            </div>`;
        } else if (server.tools.length === 0) {
            modalBody.innerHTML = `<p style="text-align: center; color: #8c8c8c; padding: 20px;">该服务器暂无可用工具</p>`;
        } else {
            server.tools.forEach(tool => {
                const toolEl = document.createElement('div');
                toolEl.className = 'tool-item';
                toolEl.innerHTML = `
                    <span class="tool-name">${tool.name}</span>
                    <p class="tool-desc">${tool.description || '无描述'}</p>
                    <div class="tool-schema"><strong>参数模式:</strong>\n${JSON.stringify(tool.input_schema, null, 2)}</div>
                `;
                modalBody.appendChild(toolEl);
            });
        }
        
        toolModal.style.display = 'flex';
    }

    closeModal.addEventListener('click', () => {
        toolModal.style.display = 'none';
    });

    window.addEventListener('click', (e) => {
        if (e.target === toolModal) {
            toolModal.style.display = 'none';
        }
    });

    // 初始化加载
    loadMCPServers();
    loadSessions();
    loadHistory();

    async function loadHistory(sessionId = null) {
        try {
            let url = config.historyUrl;
            if (sessionId) {
                url += `?session_id=${sessionId}`;
            }
            const response = await fetch(url);
            const data = await response.json();
            
            // 清空当前聊天容器
            chatContainer.innerHTML = '';
            chatHistory = [];
            welcomeMessage.style.display = 'block';

            if (data.session_id) {
                currentSessionId = data.session_id;
                currentSessionTitle.innerText = data.title || 'crewAI 智能体演示';
                // 确保列表中的状态也是正确的
                loadSessions();
            }
            
            if (data.history && data.history.length > 0) {
                welcomeMessage.style.display = 'none';
                
                // 按顺序渲染历史消息
                for (let i = 0; i < data.history.length; i++) {
                    const msg = data.history[i];
                    if (msg.role === 'user') {
                        // 如果下一条是 agent，我们把它们成对渲染
                        const nextMsg = data.history[i+1];
                        if (nextMsg && nextMsg.role === 'agent') {
                            renderHistoryPair(msg.content, nextMsg.content, nextMsg.logs);
                            i++; // 跳过下一条
                        } else {
                            renderHistoryPair(msg.content, null, null);
                        }
                    }
                }
                scrollToBottom();
            }
        } catch (error) {
            console.error('Failed to load history:', error);
        }
    }

    function renderHistoryPair(userQuery, agentResult, logs) {
        const els = createNewMessagePair(userQuery);
        chatHistory.push({ role: 'user', content: userQuery });
        
        if (agentResult || logs) {
            els.thinkingProcess.style.display = 'none';
            els.loadingIndicator.style.display = 'none';
            
            if (logs && logs.length > 0) {
                els.thinkingProcess.style.display = 'block';
                els.logContent.innerHTML = parseLogs(logs);
            }
            
            if (agentResult) {
                els.resultContainer.style.display = 'block';
                els.resultContent.innerHTML = marked.parse(agentResult);
                chatHistory.push({ role: 'agent', content: agentResult });
            }
        }
    }

    // Enter 键提交，Shift+Enter 换行
    queryInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            form.dispatchEvent(new Event('submit'));
        }
    });

    // 滚动到底部函数
    function scrollToBottom() {
        scrollArea.scrollTo({
            top: scrollArea.scrollHeight,
            behavior: 'smooth'
        });
    }

    // 滚动日志区域到底部
    function scrollLogsToBottom() {
        if (currentElements && currentElements.logContent) {
            currentElements.logContent.scrollTop = currentElements.logContent.scrollHeight;
        }
    }

    function createNewMessagePair(query) {
        // 创建用户消息
        const userMsg = userMessageTemplate.cloneNode(true);
        userMsg.classList.remove('user-message-template');
        userMsg.style.display = 'flex';
        userMsg.querySelector('.user-query-text').innerHTML = marked.parse(query);
        chatContainer.appendChild(userMsg);

        // 创建状态和结果容器
        const statusContainer = statusContainerTemplate.cloneNode(true);
        statusContainer.classList.remove('status-container-template');
        chatContainer.appendChild(statusContainer);

        const els = {
            statusContainer: statusContainer,
            statusBadge: statusContainer.querySelector('.status-badge'),
            thinkingProcess: statusContainer.querySelector('.thinking-process'),
            thinkingDots: statusContainer.querySelector('.thinking-dots'),
            logContent: statusContainer.querySelector('.log-content'),
            hitlContainer: statusContainer.querySelector('.hitl-container'),
            hitlPrompt: statusContainer.querySelector('.hitl-prompt'),
            hitlInput: statusContainer.querySelector('.hitl-input'),
            hitlSubmit: statusContainer.querySelector('.hitl-submit'),
            resultContainer: statusContainer.querySelector('.result-container'),
            resultContent: statusContainer.querySelector('.result-content'),
            loadingIndicator: statusContainer.querySelector('.loading-indicator')
        };

        // 为新的 HITL 按钮绑定事件
        els.hitlSubmit.addEventListener('click', () => handleHitlSubmit(els));
        
        // HITL 输入框回车支持
        els.hitlInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') els.hitlSubmit.click();
        });

        return els;
    }

    async function handleHitlSubmit(els) {
        const input = els.hitlInput.value.trim();
        if (!input) return;

        els.hitlSubmit.disabled = true;
        try {
            // Append human input to logs with avatar
            const userAvatar = config.userAvatar;
            const isImage = userAvatar.startsWith('http') || userAvatar.startsWith('/') || userAvatar.includes('.');

            const humanLog = document.createElement('div');
            humanLog.style.margin = '15px 0';
            humanLog.style.display = 'flex';
            humanLog.style.gap = '12px';
            humanLog.style.alignItems = 'flex-start';
            humanLog.style.flexDirection = 'row-reverse';
            humanLog.style.alignSelf = 'flex-end';
            humanLog.style.marginLeft = 'auto';
            humanLog.style.maxWidth = '90%';
            
            const avatarHtml = isImage 
                ? `<img src="${userAvatar}" style="width: 32px; height: 32px; border-radius: 50%; object-fit: cover; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">`
                : `<div style="width: 32px; height: 32px; border-radius: 50%; background: #1890ff; color: #fff; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">${userAvatar}</div>`;

            humanLog.innerHTML = `
                ${avatarHtml}
                <div style="flex: 1; background: #fffbe6; border: 1px solid #ffe58f; border-radius: 12px 0 12px 12px; padding: 10px 14px; box-shadow: 0 2px 6px rgba(0,0,0,0.05); text-align: right;" class="markdown-body">
                    ${marked.parse(input)}
                </div>
            `;
            els.logContent.appendChild(humanLog);
            humanLog.scrollIntoView({ behavior: 'smooth' });

            const response = await fetch(`/oauth/crewai/input/${currentRunId}/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': config.csrfToken
                },
                body: JSON.stringify({ input })
            });

            const data = await response.json();
            if (data.status === 'ok') {
                els.hitlContainer.style.display = 'none';
                els.hitlInput.value = '';
                els.loadingIndicator.style.display = 'block';
            }
        } catch (err) {
            showError(err.message);
        } finally {
            els.hitlSubmit.disabled = false;
        }
    }

    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        const query = queryInput.value.trim();
        if (!query) return;

        // Reset UI for new message
        submitBtn.style.display = 'none';
        stopBtn.style.display = 'flex';
        stopBtn.disabled = false;
        welcomeMessage.style.display = 'none';
        
        // 创建新的消息对
        currentElements = createNewMessagePair(query);
        
        // Reset thinking process
        currentElements.thinkingProcess.style.display = 'block';
        currentElements.logContent.innerHTML = '<div style="color: #8c8c8c; font-style: italic;">准备开始任务...</div>';
        lastLogsJson = ''; // 重置日志追踪
        updateStatus('running');
        
        // 清空并重置输入框高度
        queryInput.value = '';
        queryInput.style.height = 'auto';
        
        scrollToBottom();

        try {
            const response = await fetch(config.runUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': config.csrfToken
                },
                body: JSON.stringify({ 
                    query: query,
                    history: chatHistory,
                    session_id: currentSessionId
                })
            });

            const data = await response.json();
            if (data.error) throw new Error(data.error);

            // 如果后端返回了新的 session_id (例如自动创建的)，更新它
            if (data.session_id && currentSessionId != data.session_id) {
                currentSessionId = data.session_id;
                loadSessions();
            }

            // 将用户消息加入历史
            chatHistory.push({ role: 'user', content: query });

            currentRunId = data.run_id;
            startPolling();
        } catch (err) {
            showError(err.message);
        }
    });

    stopBtn.addEventListener('click', async function() {
        if (!currentRunId || !currentElements) return;
        
        stopBtn.disabled = true;
        stopBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i><span>正在停止...</span>';
        
        try {
            const response = await fetch(`/oauth/crewai/stop/${currentRunId}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': config.csrfToken
                }
            });
            const data = await response.json();
            if (data.status === 'ok') {
                updateStatus('stopped');
                stopPolling();
                currentElements.loadingIndicator.style.display = 'none';
                submitBtn.style.display = 'flex';
                submitBtn.disabled = false;
                stopBtn.style.display = 'none';
                stopBtn.innerHTML = '<i class="fas fa-stop-circle"></i><span>停止</span>';
            }
        } catch (err) {
            console.error('Stop error:', err);
            showError('停止失败: ' + err.message);
        }
    });

    function startPolling() {
        if (pollInterval) clearInterval(pollInterval);
        pollInterval = setInterval(checkStatus, 2000);
    }

    function stopPolling() {
        if (pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
        }
    }

    async function checkStatus() {
        if (!currentRunId || !currentElements) return;

        try {
            const response = await fetch(`/oauth/crewai/status/${currentRunId}/`);
            const data = await response.json();

            updateStatus(data.status);
            
            // Update logs with parsing
            if (data.logs && data.logs.length > 0) {
                const logsJson = JSON.stringify(data.logs);
                // 只有当日志内容真正发生变化时才更新 DOM，避免页面抖动
                if (logsJson !== lastLogsJson) {
                    const isScrolledToBottom = scrollArea.scrollHeight - scrollArea.clientHeight <= scrollArea.scrollTop + 50;
                    currentElements.logContent.innerHTML = parseLogs(data.logs);
                    lastLogsJson = logsJson;
                    
                    // 自动滚动日志展示区域到最新内容
                    scrollLogsToBottom();
                    
                    if (isScrolledToBottom) {
                        scrollToBottom();
                    }
                }
            }

            if (data.status === 'waiting') {
                currentElements.loadingIndicator.style.display = 'none';
                currentElements.hitlContainer.style.display = 'block';
                currentElements.hitlPrompt.innerText = data.prompt || '智能体需要您的反馈以继续。';
                scrollToBottom();
            } else if (data.status === 'completed') {
                stopPolling();
                currentElements.loadingIndicator.style.display = 'none';
                currentElements.resultContainer.style.display = 'block';
                currentElements.resultContent.innerHTML = marked.parse(data.result || '');
                
                // 将 Agent 的回复加入历史
                chatHistory.push({ role: 'agent', content: data.result || '' });
                
                // 运行完成后刷新会话列表，因为标题可能已更新
                loadSessions();
                
                submitBtn.style.display = 'flex';
                submitBtn.disabled = false;
                stopBtn.style.display = 'none';
                scrollToBottom();
            } else if (data.status === 'error' || data.status === 'stopped') {
                stopPolling();
                currentElements.loadingIndicator.style.display = 'none';
                if (data.status === 'error') {
                    showError(data.result);
                } else {
                    currentElements.logContent.innerHTML += '<div style="color: #ff4d4f; font-style: italic; text-align: center; margin-top: 10px;">任务已手动停止。</div>';
                    scrollLogsToBottom();
                }
                submitBtn.style.display = 'flex';
                submitBtn.disabled = false;
                stopBtn.style.display = 'none';
                scrollToBottom();
            }
        } catch (err) {
            console.error('Polling error:', err);
        }
    }

    function parseLogs(logs) {
        if (!Array.isArray(logs)) return '';
        
        let html = '';
        const userAvatar = config.userAvatar;
        const isImage = userAvatar.startsWith('http') || userAvatar.startsWith('/') || userAvatar.includes('.');
        const avatarHtml = isImage 
            ? `<img src="${userAvatar}" style="width: 32px; height: 32px; border-radius: 50%; object-fit: cover; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">`
            : `<div style="width: 32px; height: 32px; border-radius: 50%; background: #1890ff; color: #fff; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">${userAvatar}</div>`;

        logs.forEach(log => {
            let title = log.title || '信息';
            let content = log.content || '';
            let type = 'info';
            let icon = 'fas fa-info-circle';
            let bubbleStyle = '';
            let containerStyle = 'align-self: flex-start; max-width: 95%;';
            let titleColor = '#595959';
            let showAvatar = false;

            // 根据标题判断消息类型
            if (title === '人类反馈') {
                type = 'human';
                icon = 'fas fa-user';
                containerStyle = 'align-self: flex-end; max-width: 90%; margin-left: auto; display: flex; flex-direction: row-reverse; gap: 12px; align-items: flex-start;';
                bubbleStyle = `flex: 1; background: #fffbe6; border: 1px solid #ffe58f; border-radius: 16px 0 16px 16px; padding: 12px 16px; box-shadow: 0 2px 6px rgba(0,0,0,0.05); text-align: right;`;
                titleColor = '#856404';
                showAvatar = true;
                title = ''; 
            } else if (title.includes('Working Agent') || title === '智能体角色') {
                type = 'agent';
                icon = 'fas fa-user-robot';
                bubbleStyle = `background: #e6f7ff; border: 1px solid #91d5ff; border-radius: 0 16px 16px 16px; padding: 12px 16px; box-shadow: 0 2px 6px rgba(24,144,255,0.08);`;
                titleColor = '#1890ff';
            } else if (title.includes('Task') || title === '当前任务' || title === '任务阶段') {
                type = 'task';
                icon = 'fas fa-tasks';
                bubbleStyle = `background: #f9f0ff; border: 1px solid #d3adf7; border-radius: 0 16px 16px 16px; padding: 12px 16px; box-shadow: 0 2px 6px rgba(114,46,209,0.08);`;
                titleColor = '#722ed1';
            } else if (title === '执行工具' || title === '使用工具') {
                type = 'system';
                icon = 'fas fa-play-circle';
                bubbleStyle = `background: #e6f7ff; border: 1px solid #91d5ff; border-radius: 0 16px 16px 16px; padding: 10px 14px; box-shadow: 0 2px 6px rgba(24,144,255,0.08);`;
                titleColor = '#1890ff';
            } else if (title === '输入参数') {
                type = 'parameter';
                icon = 'fas fa-sign-in-alt';
                containerStyle = 'align-self: flex-start; max-width: 90%; margin-left: 20px;';
                bubbleStyle = `background: #f0f2f5; border: 1px solid #d9d9d9; border-radius: 8px; padding: 8px 12px; font-family: 'Monaco', monospace; font-size: 12px;`;
                titleColor = '#595959';
            } else if (title === '工具输出') {
                type = 'agent_output';
                icon = 'fas fa-robot';
                bubbleStyle = `background: #f6ffed; border: 1px solid #b7eb8f; border-radius: 0 16px 16px 16px; padding: 12px 16px; box-shadow: 0 2px 6px rgba(82,196,26,0.08);`;
                titleColor = '#52c41a';
            } else if (title === '执行错误') {
                type = 'error';
                icon = 'fas fa-exclamation-triangle';
                bubbleStyle = `background: #fff2f0; border: 1px solid #ffccc7; border-radius: 0 16px 16px 16px; padding: 12px 16px; box-shadow: 0 2px 6px rgba(255,77,79,0.08); border-left: 4px solid #ff4d4f;`;
                titleColor = '#ff4d4f';
            } else if (title === '思考中' || content.includes('Thinking:')) {
                type = 'thinking';
                icon = 'fas fa-brain';
                bubbleStyle = `background: #fff7e6; border: 1px solid #ffd591; border-radius: 0 16px 16px 16px; padding: 10px 14px; box-shadow: 0 2px 6px rgba(250,173,20,0.08); font-style: italic; color: #ad6800;`;
                titleColor = '#faad14';
                if (title !== '思考中') title = '思考中';
            } else if (title === '预期输出') {
                type = 'expected';
                icon = 'fas fa-bullseye';
                bubbleStyle = `background: #e6fffb; border: 1px solid #87e8de; border-radius: 0 16px 16px 16px; padding: 10px 14px; box-shadow: 0 2px 6px rgba(19,194,194,0.08);`;
                titleColor = '#13c2c2';
            } else {
                bubbleStyle = `background: #fff; border: 1px solid #e8e8e8; border-radius: 0 16px 16px 16px; padding: 10px 14px; box-shadow: 0 2px 4px rgba(0,0,0,0.02);`;
            }
            
            html += `
                <div style="${containerStyle} margin-bottom: 16px;" class="chat-bubble">
                    ${showAvatar ? avatarHtml : ''}
                    <div style="${bubbleStyle}">
                        ${title ? `
                        <div style="font-size: 11px; margin-bottom: 6px; font-weight: 600; color: ${titleColor}; display: flex; align-items: center; gap: 6px; ${type === 'human' ? 'justify-content: flex-end;' : ''}">
                            <i class="${icon}" style="font-size: 12px;"></i>
                            <span>${title}</span>
                        </div>
                        ` : ''}
                        <div class="markdown-body" style="font-size: 13px; line-height: 1.6; color: #262626;">${marked.parse(content)}</div>
                    </div>
                </div>
            `;
        });

        return html || '<div style="color: #8c8c8c; font-style: italic; text-align: center; padding: 20px;">智能体正在思考中...</div>';
    }

    function updateStatus(status) {
        if (!currentElements) return;
        currentElements.statusBadge.innerText = status.toUpperCase();
        if (status === 'running') {
            currentElements.statusBadge.style.background = '#e6f7ff';
            currentElements.statusBadge.style.color = '#1890ff';
            currentElements.loadingIndicator.style.display = 'block';
        } else if (status === 'waiting') {
            currentElements.statusBadge.style.background = '#fffbe6';
            currentElements.statusBadge.style.color = '#faad14';
            currentElements.loadingIndicator.style.display = 'none';
        } else if (status === 'completed') {
            currentElements.statusBadge.style.background = '#f6ffed';
            currentElements.statusBadge.style.color = '#52c41a';
            currentElements.loadingIndicator.style.display = 'none';
        } else if (status === 'error' || status === 'stopped') {
            currentElements.statusBadge.style.background = '#fff2f0';
            currentElements.statusBadge.style.color = '#ff4d4f';
            currentElements.loadingIndicator.style.display = 'none';
        }
    }

    function showError(msg) {
        const errorContainer = errorContainerTemplate.cloneNode(true);
        errorContainer.classList.remove('error-container-template');
        errorContainer.querySelector('.error-message').innerText = msg;
        chatContainer.appendChild(errorContainer);
        scrollToBottom();
    }
});
