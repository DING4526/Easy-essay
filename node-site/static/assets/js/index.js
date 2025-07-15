// 全局变量
let currentPaper = null;
let papers = [];

// DOM元素
const tabButtons = document.querySelectorAll('.nav-btn');
const tabContents = document.querySelectorAll('.tab-content');
const fileInput = document.getElementById('file-input');
const uploadArea = document.getElementById('upload-area');
const uploadBtn = document.getElementById('upload-btn');
const uploadProgress = document.getElementById('upload-progress');
const progressFill = document.getElementById('progress-fill');
const progressText = document.getElementById('progress-text');
const papersGrid = document.getElementById('papers-grid');
const refreshBtn = document.getElementById('refresh-papers');
const paperSelect = document.getElementById('paper-select');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const chatMessages = document.getElementById('chat-messages');
const modal = document.getElementById('paper-modal');
const modalClose = document.getElementById('modal-close');
const loading = document.getElementById('loading');
const notification = document.getElementById('notification');

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    initEventListeners();
    loadPapers();
});

// 事件监听器
function initEventListeners() {
    // 标签切换
    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });

    // 文件上传
    uploadArea.addEventListener('click', () => fileInput.click());
    uploadArea.addEventListener('dragover', handleDragOver);
    uploadArea.addEventListener('drop', handleDrop);
    fileInput.addEventListener('change', handleFileSelect);
    uploadBtn.addEventListener('click', uploadFile);

    // 论文管理
    refreshBtn.addEventListener('click', loadPapers);

    // 聊天功能
    paperSelect.addEventListener('change', selectPaper);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });
    sendBtn.addEventListener('click', sendMessage);

    // 模态框
    modalClose.addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeModal();
    });

    // 通知关闭
    document.getElementById('notification-close').addEventListener('click', hideNotification);
}

// 标签切换
function switchTab(tabName) {
    tabButtons.forEach(btn => btn.classList.remove('active'));
    tabContents.forEach(content => content.classList.remove('active'));

    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    document.getElementById(`${tabName}-tab`).classList.add('active');

    if (tabName === 'papers') {
        loadPapers();
    } else if (tabName === 'chat') {
        loadPapersForChat();
    }
}

// 文件拖拽处理
function handleDragOver(e) {
    e.preventDefault();
    uploadArea.classList.add('dragover');
}

function handleDrop(e) {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        fileInput.files = files;
        handleFileSelect();
    }
}

// 文件选择处理
function handleFileSelect() {
    const file = fileInput.files[0];
    if (file) {
        if (file.type === 'application/pdf') {
            uploadBtn.disabled = false;
            uploadArea.querySelector('span').textContent = `已选择: ${file.name}`;
        } else {
            showNotification('请选择PDF文件', 'error');
            fileInput.value = '';
        }
    }
}

// 文件上传
async function uploadFile() {
    const file = fileInput.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);
    formData.append('user_id', '1');

    showLoading();
    uploadProgress.style.display = 'block';

    try {
        const response = await fetch('http://localhost:8000/api/papers/upload', {
            method: 'POST',
            body: formData
        });
   
        const result = await response.json();

        if (response.ok) {
            showNotification('文件上传成功！开始分析...', 'success');

            // 开始分析
            await analyzePaper(result.paper_id);

            // 重置上传界面
            fileInput.value = '';
            uploadBtn.disabled = true;
            uploadArea.querySelector('span').textContent = '点击或拖拽文件到此处';
            uploadProgress.style.display = 'none';

            // 切换到论文列表
            switchTab('papers');
        } else {
            showNotification(result.error || '上传失败', 'error');
        }
    } catch (error) {
        showNotification('上传失败: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

// 分析论文
async function analyzePaper(paperId) {
    try {
        const response = await fetch(`http://localhost:8000/api/papers/${paperId}/analyze`, {
            method: 'POST'
        });

        const result = await response.json();

        if (response.ok) {
            showNotification('论文分析完成！', 'success');
        } else {
            showNotification(result.error || '分析失败', 'error');
        }
    } catch (error) {
        showNotification('分析失败: ' + error.message, 'error');
    }
}

// 加载论文列表
async function loadPapers() {
    try {
        const response = await fetch('http://localhost:8000/api/papers?user_id=1');
        const data = await response.json();

        papers = data;
        renderPapers();
    } catch (error) {
        showNotification('加载论文列表失败', 'error');
    }
}

// 渲染论文列表
function renderPapers() {
    if (papers.length === 0) {
        papersGrid.innerHTML = '<div class="empty-state">暂无论文，请先上传论文</div>';
        return;
    }

    papersGrid.innerHTML = papers.map(paper => `
        <div class="paper-card" onclick="showPaperDetails(${paper.id})">
            <div class="paper-title">${paper.title || paper.original_filename}</div>
            <div class="paper-meta">
                上传时间: ${new Date(paper.upload_time).toLocaleString()}
            </div>
            <div class="paper-status status-${paper.processing_status}">
                ${getStatusText(paper.processing_status)}
            </div>
        </div>
    `).join('');
}

// 获取状态文本
function getStatusText(status) {
    const statusMap = {
        'uploaded': '已上传',
        'processing': '分析中',
        'completed': '已完成',
        'failed': '分析失败'
    };
    return statusMap[status] || status;
}

// 显示论文详情
async function showPaperDetails(paperId) {
    try {
        const response = await fetch(`http://localhost:8000/api/papers/${paperId}`);
        const paper = await response.json();

        // 填充模态框内容
        document.getElementById('modal-title').textContent = paper.title || paper.original_filename;
        document.getElementById('detail-title').textContent = paper.title || '未提取到标题';
        document.getElementById('detail-authors').textContent = paper.authors || '未提取到作者信息';
        document.getElementById('detail-upload-time').textContent = new Date(paper.upload_time).toLocaleString();
        document.getElementById('detail-abstract').textContent = paper.abstract || '未提取到摘要';
        document.getElementById('detail-summary').textContent = paper.summary || '未生成简明摘要';
        document.getElementById('detail-key-content').textContent = paper.key_content || '未提取到关键内容';
        document.getElementById('detail-translation').textContent = paper.translation || '未生成翻译';
        document.getElementById('detail-terminology').textContent = paper.terminology || '未生成术语解释';
        document.getElementById('detail-research-context').textContent = paper.research_context || '未生成研究脉络';

        modal.classList.add('active');
    } catch (error) {
        showNotification('加载论文详情失败', 'error');
    }
}

// 关闭模态框
function closeModal() {
    modal.classList.remove('active');
}

// 加载聊天用的论文列表
async function loadPapersForChat() {
    try {
        const response = await fetch('http://localhost:8000/api/papers?user_id=1');
        const data = await response.json();

        paperSelect.innerHTML = '<option value="">选择论文...</option>';
        data.filter(p => p.processing_status === 'completed').forEach(paper => {
            const option = document.createElement('option');
            option.value = paper.id;
            option.textContent = paper.title || paper.original_filename;
            paperSelect.appendChild(option);
        });
    } catch (error) {
        showNotification('加载论文列表失败', 'error');
    }
}

// 选择论文进行聊天
function selectPaper() {
    const paperId = paperSelect.value;
    if (paperId) {
        currentPaper = paperId;
        chatInput.disabled = false;
        sendBtn.disabled = false;

        // 清空聊天记录
        chatMessages.innerHTML = `
            <div class="welcome-message">
                <i class="fas fa-robot"></i>
                <p>已选择论文，您可以开始提问了！</p>
            </div>
        `;

        // 加载聊天历史
        loadChatHistory(paperId);
    } else {
        currentPaper = null;
        chatInput.disabled = true;
        sendBtn.disabled = true;
    }
}

// 加载聊天历史
async function loadChatHistory(paperId) {
    try {
        const response = await fetch(`http://localhost:8000/api/papers/${paperId}/chat/history?user_id=1`);
        const chats = await response.json();

        if (chats.length > 0) {
            chatMessages.innerHTML = '';
            chats.forEach(chat => {
                addMessage(chat.question, 'user');
                addMessage(chat.answer, 'assistant');
            });
        }
    } catch (error) {
        console.error('加载聊天历史失败:', error);
    }
}

// 发送消息
async function sendMessage() {
    const question = chatInput.value.trim();
    if (!question || !currentPaper) return;

    // 添加用户消息
    addMessage(question, 'user');
    chatInput.value = '';

    // 显示加载状态
    const loadingMsg = addMessage('正在思考中...', 'assistant', true);

    try {
        const response = await fetch(`http://localhost:8000/api/papers/${currentPaper}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                question: question,
                user_id: 1
            })
        });

        const result = await response.json();

        // 移除加载消息
        loadingMsg.remove();

        if (response.ok) {
            addMessage(result.answer, 'assistant');
        } else {
            addMessage('抱歉，回答问题时出现错误: ' + (result.error || '未知错误'), 'assistant');
        }
    } catch (error) {
        loadingMsg.remove();
        addMessage('抱歉，网络错误，请稍后重试。', 'assistant');
    }
}

// 添加消息到聊天界面
function addMessage(content, sender, isLoading = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;

    messageDiv.innerHTML = `
        <div class="message-content">
            ${content}
        </div>
    `;

    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    return messageDiv;
}

// 显示加载状态
function showLoading() {
    loading.style.display = 'flex';
}

// 隐藏加载状态
function hideLoading() {
    loading.style.display = 'none';
}

// 显示通知
function showNotification(message, type = 'info') {
    const notificationText = document.getElementById('notification-text');
    notificationText.textContent = message;

    notification.className = `notification ${type}`;
    notification.classList.add('show');

    setTimeout(() => {
        hideNotification();
    }, 5000);
}

// 隐藏通知
function hideNotification() {
    notification.classList.remove('show');
}

