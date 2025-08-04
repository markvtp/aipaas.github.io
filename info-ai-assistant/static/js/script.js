document.addEventListener('DOMContentLoaded', function() {
    // DOM元素
    const chatMessages = document.getElementById('chatMessages');
    const userInput = document.getElementById('userInput');
    const sendButton = document.getElementById('sendButton');
    const historyToggle = document.getElementById('historyToggle');
    const historyModal = new bootstrap.Modal(document.getElementById('historyModal'));
    const historyList = document.getElementById('historyList');
    const mobileHistoryList = document.getElementById('mobileHistoryList');
    const systemStatus = document.getElementById('systemStatus');
    
    // 对话历史
    let conversationHistory = [];
    
    // 调整输入框高度
    function adjustTextareaHeight() {
        userInput.style.height = 'auto';
        userInput.style.height = (userInput.scrollHeight) + 'px';
    }
    
    userInput.addEventListener('input', adjustTextareaHeight);
    
    // 初始化
    adjustTextareaHeight();
    
    // 发送消息
    function sendMessage() {
        const message = userInput.value.trim();
        if (!message) return;
        
        // 添加用户消息到聊天区
        addMessage('user', message);
        
        // 添加到历史记录
        conversationHistory.push({
            role: 'user',
            content: message,
            timestamp: new Date().toISOString()
        });
        
        // 清空输入框并禁用按钮
        userInput.value = '';
        userInput.style.height = 'auto';
        sendButton.disabled = true;
        systemStatus.innerHTML = '状态: <span class="text-primary">思考中...</span>';
        
        // 添加AI正在输入指示
        addTypingIndicator();
        
        // 创建事件源连接
        const eventSource = new EventSource(`/chat?message=${encodeURIComponent(message)}`);
        let aiResponse = '';
        
        eventSource.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                
                // 处理正常响应
                if (data.message) {
                    aiResponse += data.message;
                    updateLastMessage('assistant', aiResponse);
                }
                
                // 处理错误
                if (data.error) {
                    updateLastMessage('assistant', `<div class="text-danger">${data.error}</div>`);
                    systemStatus.innerHTML = '状态: <span class="text-danger">错误</span>';
                    eventSource.close();
                }
                
                // 处理结束
                if (data.end) {
                    eventSource.close();
                    finishResponse(aiResponse);
                }
            } catch (e) {
                console.error('解析事件流出错:', e);
                eventSource.close();
            }
        };
        
        eventSource.onerror = function() {
            eventSource.close();
            systemStatus.innerHTML = '状态: <span class="text-danger">错误</span>';
            updateLastMessage('assistant', '<div class="text-danger">与AI助手的连接中断</div>');
        };
    }
    
    // 添加打字指示器
    function addTypingIndicator() {
        const typingHtml = `
            <div class="message ai-message" id="typingIndicator">
                <div class="message-header">
                    <div class="message-avatar">
                        <i class="fas fa-robot"></i>
                    </div>
                    <div>AI助手</div>
                </div>
                <div class="message-content">
                    <div class="typing-indicator">
                        <span></span>
                        <span></span>
                        <span></span>
                    </div>
                </div>
            </div>
        `;
        chatMessages.innerHTML += typingHtml;
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    // 更新最后一条消息（用于流式响应）
    function updateLastMessage(role, content) {
        const lastMessage = document.getElementById('typingIndicator') || 
                            document.querySelector('.message:last-child');
        
        if (lastMessage) {
            lastMessage.querySelector('.message-content').innerHTML = content;
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    }
    
    // 完成响应处理
    function finishResponse(content) {
        // 移除打字指示器
        const typingIndicator = document.getElementById('typingIndicator');
        if (typingIndicator) typingIndicator.remove();
        
        // 创建完成的AI消息
        const aiMessageHtml = createMessage('assistant', content);
        
        // 添加到聊天区
        chatMessages.innerHTML += aiMessageHtml;
        
        // 添加到历史记录
        conversationHistory.push({
            role: 'assistant',
            content: content,
            timestamp: new Date().toISOString()
        });
        
        // 更新状态
        systemStatus.innerHTML = '状态: <span class="text-success">就绪</span>';
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        // 更新历史记录列表
        updateHistoryLists();
    }
    
    // 创建消息元素
    function addMessage(role, content) {
        const messageHtml = createMessage(role, content);
        chatMessages.innerHTML += messageHtml;
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    // 创建消息HTML
    function createMessage(role, content) {
        const isAI = role === 'assistant';
        const icon = isAI ? 'fa-robot' : 'fa-user';
        const name = isAI ? 'AI助手' : '您';
        const messageClass = isAI ? 'ai-message' : 'user-message';
        
        return `
            <div class="message ${messageClass}">
                <div class="message-header">
                    <div class="message-avatar">
                        <i class="fas ${icon}"></i>
                    </div>
                    <div>${name}</div>
                </div>
                <div class="message-content">${content.replace(/\n/g, '<br>')}</div>
            </div>
        `;
    }
    
    // 更新历史记录列表
    function updateHistoryLists() {
        // 清空现有列表
        historyList.innerHTML = '';
        mobileHistoryList.innerHTML = '';
        
        // 添加历史记录（只显示用户消息）
        conversationHistory
            .filter(item => item.role === 'user')
            .forEach((item, index) => {
                const timestamp = new Date(item.timestamp);
                const timeStr = timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                const dateStr = timestamp.toLocaleDateString();
                
                const historyItem = `
                    <a href="#" class="list-group-item list-group-item-action history-item" data-index="${index}">
                        <div class="d-flex justify-content-between">
                            <span><i class="fas fa-comment me-2 text-primary"></i>${truncateText(item.content, 30)}</span>
                            <small class="text-muted">${timeStr}</small>
                        </div>
                        <small class="text-muted">${dateStr}</small>
                    </a>
                `;
                
                historyList.innerHTML += historyItem;
                mobileHistoryList.innerHTML += historyItem;
            });
        
        // 添加历史项目事件
        document.querySelectorAll('.history-item').forEach(item => {
            item.addEventListener('click', function(e) {
                e.preventDefault();
                const index = parseInt(this.getAttribute('data-index'));
                
                // 显示完整对话
                scrollToHistory(index);
                
                // 在移动端关闭模态框
                if (window.innerWidth < 992) {
                    historyModal.hide();
                }
            });
        });
    }
    
    // 滚动到历史记录
    function scrollToHistory(startIndex) {
        // 清除现有消息
        chatMessages.innerHTML = '';
        
        // 添加相关消息
        for (let i = startIndex; i < conversationHistory.length; i++) {
            const item = conversationHistory[i];
            addMessage(item.role, item.content);
        }
        
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    // 文本截断函数
    function truncateText(text, maxLength) {
        return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
    }
    
    // 事件监听
    sendButton.addEventListener('click', sendMessage);
    
    userInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    userInput.addEventListener('input', function() {
        sendButton.disabled = this.value.trim() === '';
    });
    
    historyToggle.addEventListener('click', function() {
        historyModal.show();
    });
    
    // 初始更新历史记录（如果有）
    updateHistoryLists();
    
    // 健康检查
    fetch('/health')
        .then(response => response.json())
        .then(data => {
            if (data.status === "OK") {
                systemStatus.innerHTML = '状态: <span class="text-success">就绪</span>';
            }
        })
        .catch(() => {
            systemStatus.innerHTML = '状态: <span class="text-warning">未连接</span>';
        });
});