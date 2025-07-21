// 全局变量
let currentPaper = null;
let papers = [];
let user_id = 1;

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

const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const chatMessages = document.getElementById('chat-messages');

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
    formData.append('user_id', user_id);

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
        const response = await fetch(`http://localhost:8000/api/papers?user_id=${user_id}`);
        const data = await response.json();

        papers = data;
        renderPapers();
    } catch (error) {
        showNotification('加载论文列表失败', 'error');
    }
}

// 渲染论文列表
function renderPapers() {
    let current_paper = [];
    let j=0;
    for(let i=0;i<papers.length;i++)
    {
        const paper = papers[i];
        if(paper.user_id == user_id)
        {
            current_paper[j]=paper;
            j++;
        }
    }
    if (current_paper.length === 0) {
        papersGrid.innerHTML = '<div class="empty-state">暂无论文，请先上传论文</div>';
        return;
    }

    papersGrid.innerHTML = current_paper.map(paper => `
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

        // --- 更新填充逻辑 ---
        // 核心信息 (合并后的视图)
        document.getElementById('viewer-title').innerHTML = marked.parse(paper.title || '未提取标题');
        document.getElementById('viewer-authors').innerHTML = marked.parse(paper.authors || '未提取作者');
        document.getElementById('viewer-upload-time').textContent = new Date(paper.upload_time).toLocaleString();
        document.getElementById('viewer-abstract').innerHTML = marked.parse(paper.abstract || '暂无摘要');
        document.getElementById('viewer-key-content').innerHTML = marked.parse(paper.key_content || '暂无关键内容');

        // 其他信息
        document.getElementById('viewer-translation').innerHTML = marked.parse(paper.translation || '未生成翻译');
        document.getElementById('viewer-terminology').innerHTML = marked.parse(paper.terminology || '未生成术语解释');
        document.getElementById('viewer-research-context').innerHTML = marked.parse(paper.research_context || '未生成研究脉络');

        // --- 新增：渲染相关论文 ---
        renderRelatedPapers(paper.related_papers_json);

        currentPaper = paperId;
        // ... (保留聊天功能绑定)
    } catch (error) {
        showNotification('加载论文详情失败', 'error');
        console.error(error);
    }
}

// document.addEventListener('DOMContentLoaded', () => {
//   const tabButtons = document.querySelectorAll('.viewer-tab-btn');
//   const sections = document.querySelectorAll('.viewer-section');
//
//   tabButtons.forEach(btn => {
//     btn.addEventListener('click', () => {
//       const target = btn.dataset.target;
//
//       // 1. 切换按钮高亮
//       tabButtons.forEach(b => b.classList.remove('active'));
//       btn.classList.add('active');
//
//       // 2. 显示对应的内容块，隐藏其他
//       sections.forEach(sec => {
//         if (sec.dataset.section === target) {
//           sec.style.display = 'block';
//         } else {
//           sec.style.display = 'none';
//         }
//       });
//     });
//   });
// });

// 更新 Tab 切换的JS逻辑
// 确保这个逻辑在 DOMContentLoaded 之后运行
document.addEventListener('DOMContentLoaded', () => {
    // 使用 event delegation 来处理按钮点击
    const viewerNav = document.querySelector('.viewer-nav');
    if (viewerNav) {
        viewerNav.addEventListener('click', (e) => {
            if (e.target.matches('.viewer-tab-btn')) {
                const btn = e.target;
                const target = btn.dataset.target;

                // 切换按钮高亮
                document.querySelectorAll('.viewer-tab-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');

                // 显示对应内容块
                document.querySelectorAll('.viewer-section').forEach(sec => {
                    sec.style.display = (sec.dataset.section === target) ? 'block' : 'none';
                });
            }
        });
    }
  });

// 加载聊天历史
async function loadChatHistory(paperId) {
    try {
        const response = await fetch(`http://localhost:8000/api/papers/${paperId}/chat/history?user_id=${user_id}`);
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
                user_id: user_id
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

// // 添加消息到聊天界面
// function addMessage(content, sender, isLoading = false) {
//     const chatMessages = document.getElementById('chat-messages'); //确保每次重新获取
//     const messageDiv = document.createElement('div');
//     messageDiv.className = `message ${sender}`;
//
//     messageDiv.innerHTML = `
//         <div class="message-content">
//             ${content}
//         </div>
//     `;
//
//     chatMessages.appendChild(messageDiv);
//     chatMessages.scrollTop = chatMessages.scrollHeight;
//
//     return messageDiv;
// }

//修改addmessage函数，解析问答返回的json，并且对有图像和没图像进行处理
// 添加消息到聊天界面
// --- 修改：addMessage 函数，增加“放大”按钮和直接的事件绑定 ---
function addMessage(content, sender, isLoading = false) {
    const chatMessages = document.getElementById('chat-messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;

    let messageContentHTML = '';

    if (sender === 'assistant' && !isLoading) {
        try {
            const data = JSON.parse(content);
            if (data.diagram && data.diagram.type === 'mermaid') {
                const diagramId = `mermaid-${Date.now()}`;
                const diagramCode = data.diagram.code;
                const diagramTitle = data.diagram.title || '生成的图表';

                // --- 修改：添加“放大”按钮，并用一个容器包裹按钮 ---
                messageContentHTML = `
                    <div class="message-content">
                        ${data.answer ? marked.parse(data.answer) : ''}
                        <div class="diagram-container">
                            <div class="diagram-header">
                                <h4>${diagramTitle}</h4>
                                <div class="diagram-actions">
                                    <button class="btn-action btn-enlarge" title="在新标签页中打开">
                                        <i class="fas fa-search-plus"></i> 放大
                                    </button>
                                    <button class="btn-action btn-download" title="下载为PNG图片">
                                        <i class="fas fa-download"></i> 下载
                                    </button>
                                </div>
                            </div>
                            <div class="mermaid" id="${diagramId}">${diagramCode}</div>
                        </div>
                    </div>
                `;

                messageDiv.innerHTML = messageContentHTML;
                chatMessages.appendChild(messageDiv);

                // 异步渲染 Mermaid 图表，并直接绑定事件
                setTimeout(() => {
                    try {
                        mermaid.run({ nodes: [document.getElementById(diagramId)] });

                        // --- 修改：直接为新创建的按钮绑定事件 ---
                        const enlargeBtn = messageDiv.querySelector('.btn-enlarge');
                        enlargeBtn.addEventListener('click', () => enlargeDiagram(diagramId));

                        const downloadBtn = messageDiv.querySelector('.btn-download');
                        downloadBtn.addEventListener('click', () => downloadDiagram(diagramId, diagramTitle));

                    } catch(e) {
                        console.error("Mermaid渲染失败:", e);
                        const diagramNode = document.getElementById(diagramId);
                        if(diagramNode) diagramNode.innerText = "图表渲染失败，请检查Mermaid代码。";
                    }
                }, 100);

            } else {
                messageContentHTML = `<div class="message-content">${marked.parse(data.answer || content)}</div>`;
                messageDiv.innerHTML = messageContentHTML;
                chatMessages.appendChild(messageDiv);
            }
        } catch (e) {
            messageContentHTML = `<div class="message-content">${marked.parse(content)}</div>`;
            messageDiv.innerHTML = messageContentHTML;
            chatMessages.appendChild(messageDiv);
        }
    } else {
        messageContentHTML = `<div class="message-content">${isLoading ? content : marked.parse(content)}</div>`;
        messageDiv.innerHTML = messageContentHTML;
        chatMessages.appendChild(messageDiv);
    }

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

// --- 新增：渲染相关论文的函数 ---
function renderRelatedPapers(relatedDataJson) {
    const container = document.getElementById('viewer-related-papers');
    if (!relatedDataJson) {
        container.innerHTML = '<p>暂无相关论文信息。</p>';
        return;
    }

    try {
        // 如果后端返回的是特定错误消息字符串，直接显示它
        if (typeof relatedDataJson === 'string' && relatedDataJson.includes('无法查询到该论文')) {
            container.innerHTML = `<p class="related-paper-error">${relatedDataJson}</p>`;
            return;
        }

        // 解析JSON字符串
        const data = JSON.parse(relatedDataJson);
        const { references, citations } = data;

        let html = '';

        // 渲染引用本文的文献 (Citations)
        if (citations && citations.length > 0) {
            html += '<h5>引用本文的文献 (Citations):</h5>';
            html += '<ul class="related-papers-list">';
            citations.forEach(paper => {
                // 使用模板字符串构建列表项，并为每个元素添加类名方便CSS选择
                html += `
                    <li class="related-paper-item" onclick="alert('功能待开发：即将分析: ${paper.title.replace(/'/g, "\\'")}')">
                        <div class="related-paper-title">${paper.title || 'N/A'}</div>
                        <div class="related-paper-meta">
                            <span class="meta-item"><strong>年份:</strong> ${paper.publicationDate || 'N/A'}</span>
                            <span class="meta-item"><strong>引用数:</strong> ${paper.citationCount || 0}</span>
                        </div>
                    </li>
                `;
            });
            html += '</ul>';
        }

        // 渲染本文引用的文献 (References)
        if (references && references.length > 0) {
            html += '<h5>本文引用的文献 (References):</h5>';
            html += '<ul class="related-papers-list">';
            references.forEach(paper => {
                html += `
                    <li class="related-paper-item" onclick="alert('功能待开发：即将分析: ${paper.title.replace(/'/g, "\\'")}')">
                        <div class="related-paper-title">${paper.title || 'N/A'}</div>
                        <div class="related-paper-meta">
                            <span class="meta-item"><strong>年份:</strong> ${paper.publicationDate || 'N/A'}</span>
                            <span class="meta-item"><strong>引用数:</strong> ${paper.citationCount || 0}</span>
                        </div>
                    </li>
                `;
            });
            html += '</ul>';
        }

        // 如果没有任何相关论文信息
        if (!html) {
            html = '<p>未找到相关的引用或被引文献。</p>';
        }

        container.innerHTML = html;

    } catch (error) {
        // 捕获JSON解析错误或其他运行时错误
        console.error("解析或渲染相关论文数据失败:", error);
        container.innerHTML = '<p class="related-paper-error">加载相关论文信息时出错，请检查数据格式。</p>';
    }
}

function enlargeDiagram(diagramId) {
    const svgElement = document.querySelector(`#${diagramId} > svg`);
    if (!svgElement) {
        showNotification('找不到图表以放大，请稍候。', 'error');
        return;
    }

    // 1. 获取SVG的完整代码字符串
    const svgString = new XMLSerializer().serializeToString(svgElement);

    // 2. 创建一个包含SVG和居中样式的完整HTML文档字符串
    const htmlContent = `
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Diagram Viewer</title>
            <style>
                /* 在这个新页面中应用样式 */
                html, body {
                    margin: 0;
                    padding: 0;
                    width: 100%;
                    height: 100%;
                    display: flex;
                    justify-content: center; /* 水平居中 */
                    align-items: center;   /* 垂直居中 */
                    background-color: #f0f2f5; /* 添加一个舒适的背景色 */
                }
                svg {
                    /* 确保SVG不会超出屏幕 */
                    max-width: 95%;
                    max-height: 95%;
                }
            </style>
        </head>
        <body>
            <!-- 将SVG代码直接嵌入到body中 -->
            ${svgString}
        </body>
        </html>
    `;

    // 3. 创建一个类型为 'text/html' 的Blob
    const blob = new Blob([htmlContent], {type: 'text/html'});
    const url = URL.createObjectURL(blob);

    // 4. 在新标签页中打开这个HTML页面
    const newWindow = window.open(url, '_blank');

    if (!newWindow) {
        showNotification('无法打开新窗口，请检查您的弹窗拦截设置。', 'error');
    }
}

// --- 下载图表的函数<没实现> ---
async function downloadDiagram(diagramId, filename) {
    showNotification('正在生成图片...', 'info');
    try {
        const svgElement = document.querySelector(`#${diagramId} > svg`);
        if (!svgElement) {
            showNotification('找不到图表元素，无法下载', 'error');
            return;
        }

        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        const svgString = new XMLSerializer().serializeToString(svgElement);

        // 使用 canvg 将 SVG 渲染到 Canvas 上
        const v = await Canvg.from(ctx, svgString);

        // 添加一些内边距，让下载的图片更好看
        const padding = 20;
        canvas.width = v.width + padding * 2;
        canvas.height = v.height + padding * 2;

        // 填充白色背景
        ctx.fillStyle = '#FFFFFF';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // 在画布上渲染SVG，并应用内边距
        await v.render({
            offsetX: padding,
            offsetY: padding
        });

        // 创建下载链接
        const link = document.createElement('a');
        link.href = canvas.toDataURL('image/png');
        // 清理文件名中的非法字符
        link.download = `${filename.replace(/[\s/\\?%*:|"<>]/g, '_')}.png`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        showNotification('图片已开始下载！', 'success');

    } catch (error) {
        console.error('下载图表失败:', error);
        showNotification('下载失败，请查看控制台错误信息', 'error');
    }
}


    // 注册表单提交
document.getElementById('register-form').addEventListener('submit', async function (e) {
    e.preventDefault();
    const username = document.getElementById('register-username').value;
    const email = document.getElementById('register-email').value;

    try {
        const res = await fetch('http://localhost:8000/api/users/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, email })
        });
        const data = await res.json();
        alert('注册成功: ' + data.username);
        //清空输入框
        document.getElementById('register-username').value = '';
        document.getElementById('register-email').value = '';
    } catch (err) {
        alert('注册失败');
        //清空输入框
        document.getElementById('register-username').value = '';
        document.getElementById('register-email').value = '';
    }
});

// 登录表单提交
document.getElementById('login-form').addEventListener('submit', async function (e) {
    e.preventDefault();
    const username = document.getElementById('login-username').value;
    const email = document.getElementById('login-email').value;

    try {
        const res = await fetch('http://localhost:8000/api/users/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, email })
        });
        const data = await res.json();
        alert('登录成功: ' + data.username);
        console.log("here");
        user_id = data.id;
        document.getElementById('current-user').textContent = data.username;
        //清空输入框
        document.getElementById('login-username').value = '';
        document.getElementById('login-email').value = '';
    } catch (err) {
        alert('登录失败');
        console.error("登录",err)
        //清空输入框
        document.getElementById('login-username').value = '';
        document.getElementById('login-email').value = '';
    }
});


