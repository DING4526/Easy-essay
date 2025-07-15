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
    //paperSelect.addEventListener('change', selectPaper);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });
    console.log('sendBtn');
    sendBtn.addEventListener('click', sendMessage);

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


async function showPaperDetails(paperId) {
    try {
        const response = await fetch(`http://localhost:8000/api/papers/${paperId}`);
        const paper = await response.json();

        // 切换 tab 显示
        document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
        document.getElementById('viewer-tab').classList.add('active');

        // 设置 PDF iframe
        document.getElementById('pdf-frame').src = `http://localhost:8000/uploads/${encodeURIComponent(paper.filename || paper.original_filename)}`;

        // 填充信息
        //基本信息
        /*document.getElementById('viewer-title').textContent = paper.title || '未提取标题';
        document.getElementById('viewer-authors').textContent = paper.authors || '未提取作者';
        document.getElementById('viewer-upload-time').textContent = new Date(paper.upload_time).toLocaleString();
        //摘要
        document.getElementById('viewer-abstract').textContent = paper.abstract || '暂无摘要';
        //关键内容
        document.getElementById('viewer-key-content').textContent = paper.key_content || '暂无关键内容';
        //中文翻译
        document.getElementById('viewer-translation').textContent = paper.translation || '未生成翻译';
        //术语解释
        document.getElementById('viewer-terminology').textContent = paper.terminology || '未生成术语解释';
        //研究脉络
        document.getElementById('viewer-research-context').textContent = paper.research_context || '未生成研究脉络'*/

        //添加markdown渲染
        //基本信息
        document.getElementById('viewer-title').innerHTML = marked.parse(paper.title || '未提取标题');
        document.getElementById('viewer-authors').innerHTML = marked.parse(paper.authors || '未提取作者');
        document.getElementById('viewer-upload-time').textContent = new Date(paper.upload_time).toLocaleString(); //时间不需要
        //摘要
        document.getElementById('viewer-abstract').innerHTML = marked.parse(paper.abstract || '暂无摘要');
        //关键内容
        document.getElementById('viewer-key-content').innerHTML = marked.parse(paper.key_content || '暂无关键内容');
        //中文翻译
        document.getElementById('viewer-translation').innerHTML = marked.parse(paper.translation || '未生成翻译');
        //术语解释
        document.getElementById('viewer-terminology').innerHTML = marked.parse(paper.terminology || '未生成术语解释');
        //研究脉络
        document.getElementById('viewer-research-context').innerHTML = marked.parse(paper.research_context || '未生成研究脉络');

        currentPaper = paperId;
        // 绑定聊天输入框事件
        document.getElementById('send-btn').onclick = sendMessage;
        document.getElementById('chat-input').onkeypress = (e) => {
            if (e.key === 'Enter') sendMessage();
        };
    } catch (error) {
        showNotification('加载论文详情失败', 'error');
    }
}
document.addEventListener('DOMContentLoaded', () => {
  const tabButtons = document.querySelectorAll('.viewer-tab-btn');
  const sections = document.querySelectorAll('.viewer-section');

  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.target;

      // 1. 切换按钮高亮
      tabButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      // 2. 显示对应的内容块，隐藏其他
      sections.forEach(sec => {
        if (sec.dataset.section === target) {
          sec.style.display = 'block';
        } else {
          sec.style.display = 'none';
        }
      });
    });
  });
});

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
    const chatInput = document.getElementById('chat-input');
    const chatMessages = document.getElementById('chat-messages');
    //sendBtn.disabled = false; // 禁用发送按钮
    console.log('发送消息');
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
    const chatMessages = document.getElementById('chat-messages'); //确保每次重新获取
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

