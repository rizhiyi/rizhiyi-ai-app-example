document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('agent-form');
    const queryInput = document.getElementById('query');
    const submitBtn = document.getElementById('submit-btn');
    const stopBtn = document.getElementById('stop-btn');
    const scrollArea = document.getElementById('chat-scroll-area');
    const welcomeMessage = document.getElementById('welcome-message');
    const statusContainer = document.getElementById('status-container');
    const statusBadge = document.getElementById('status-badge');
    const hitlContainer = document.getElementById('hitl-container');
    const hitlPrompt = document.getElementById('hitl-prompt');
    const hitlInput = document.getElementById('hitl-input');
    const hitlSubmit = document.getElementById('hitl-submit');
    const userMessage = document.getElementById('user-message');
    const userQueryText = document.getElementById('user-query-text');
    const thinkingProcess = document.getElementById('thinking-process');
    const resultContainer = document.getElementById('result-container');
    const resultContent = document.getElementById('result-content');
    const loadingIndicator = document.getElementById('loading-indicator');
    const logContent = document.getElementById('log-content');
    const errorContainer = document.getElementById('error-container');
    const errorMessage = document.getElementById('error-message');
    const mcpContainer = document.getElementById('mcp-servers-container');
    const mcpLoading = document.getElementById('mcp-loading');
    const toolModal = document.getElementById('tool-modal');
    const modalTitle = document.getElementById('modal-title');
    const modalBody = document.getElementById('modal-body');
    const closeModal = document.getElementById('close-modal');
    
    // 获取配置
    const config = window.CrewAIConfig || {};

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

    // 自动调整输入框高度
    queryInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
    });

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

    // Enter 键提交，Shift+Enter 换行
    queryInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            form.dispatchEvent(new Event('submit'));
        }
    });

    // 滚动到底部函数
    function scrollToBottom() {
        scrollArea.scrollTop = scrollArea.scrollHeight;
    }

    // 滚动日志区域到底部
    function scrollLogsToBottom() {
        if (logContent) {
            logContent.scrollTop = logContent.scrollHeight;
        }
    }

    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        const query = queryInput.value.trim();
        if (!query) return;

        // Reset UI
        submitBtn.style.display = 'none';
        stopBtn.style.display = 'flex';
        stopBtn.disabled = false;
        welcomeMessage.style.display = 'none';
        errorContainer.style.display = 'none';
        resultContainer.style.display = 'none';
        hitlContainer.style.display = 'none';
        statusContainer.style.display = 'block';
        loadingIndicator.style.display = 'block';
        
        // Show user message
        userMessage.style.display = 'flex';
        userQueryText.innerHTML = marked.parse(query);
        userQueryText.classList.add('markdown-body');
        
        // Reset thinking process
        thinkingProcess.style.display = 'block';
        logContent.innerHTML = '<div style="color: #8c8c8c; font-style: italic;">准备开始任务...</div>';
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
                body: JSON.stringify({ query })
            });

            const data = await response.json();
            if (data.error) throw new Error(data.error);

            currentRunId = data.run_id;
            startPolling();
        } catch (err) {
            showError(err.message);
        }
    });

    stopBtn.addEventListener('click', async function() {
        if (!currentRunId) return;
        
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
                loadingIndicator.style.display = 'none';
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

    hitlSubmit.addEventListener('click', async function() {
        const input = hitlInput.value.trim();
        if (!input) return;

        hitlSubmit.disabled = true;
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
            logContent.appendChild(humanLog);
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
                hitlContainer.style.display = 'none';
                hitlInput.value = '';
                loadingIndicator.style.display = 'block';
            }
        } catch (err) {
            showError(err.message);
        } finally {
            hitlSubmit.disabled = false;
        }
    });

    function startPolling() {
        if (pollInterval) clearInterval(pollInterval);
        pollInterval = setInterval(checkStatus, 2000);
    }

    async function checkStatus() {
        if (!currentRunId) return;

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
                    logContent.innerHTML = parseLogs(data.logs);
                    lastLogsJson = logsJson;
                    
                    // 自动滚动日志展示区域到最新内容
                    scrollLogsToBottom();
                    
                    if (isScrolledToBottom) {
                        scrollToBottom();
                    }
                }
            }

            if (data.status === 'waiting') {
                loadingIndicator.style.display = 'none';
                hitlContainer.style.display = 'block';
                hitlPrompt.innerText = data.prompt || '智能体需要您的反馈以继续。';
                scrollToBottom();
            } else if (data.status === 'completed') {
                stopPolling();
                loadingIndicator.style.display = 'none';
                resultContainer.style.display = 'block';
                resultContent.innerHTML = marked.parse(data.result || '');
                submitBtn.style.display = 'flex';
                submitBtn.disabled = false;
                stopBtn.style.display = 'none';
                scrollToBottom();
            } else if (data.status === 'error' || data.status === 'stopped') {
                stopPolling();
                loadingIndicator.style.display = 'none';
                if (data.status === 'error') {
                    showError(data.result);
                } else {
                    logContent.innerHTML += '<div style="color: #ff4d4f; font-style: italic; text-align: center; margin-top: 10px;">任务已手动停止。</div>';
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

    function stopPolling() {
        clearInterval(pollInterval);
        pollInterval = null;
    }

    function updateStatus(status) {
        statusBadge.innerText = status.toUpperCase();
        if (status === 'running') {
            statusBadge.style.background = '#e6f7ff';
            statusBadge.style.color = '#1890ff';
        } else if (status === 'waiting') {
            statusBadge.style.background = '#fff7e6';
            statusBadge.style.color = '#fa8c16';
        } else if (status === 'completed') {
            statusBadge.style.background = '#f6ffed';
            statusBadge.style.color = '#52c41a';
        } else if (status === 'stopped') {
            statusBadge.style.background = '#f5f5f5';
            statusBadge.style.color = '#8c8c8c';
        } else {
            statusBadge.style.background = '#fff2f0';
            statusBadge.style.color = '#ff4d4f';
        }
    }

    function showError(msg) {
        errorContainer.style.display = 'block';
        errorMessage.innerText = msg;
        loadingIndicator.style.display = 'none';
        submitBtn.style.display = 'flex';
        submitBtn.disabled = false;
        stopBtn.style.display = 'none';
        scrollToBottom();
    }
});
