document.querySelector("#btn-fold-in").addEventListener("click", (e) => {
    const sidebar = document.querySelector(".sidebar");
    sidebar.style.width = 0

    const btnFoldOut = document.querySelector("#btn-fold-out");
    btnFoldOut.style.display = "inline-block"
})

document.querySelector("#input-send").addEventListener("click", (e) => {
    sendRequest(uri = "/chain/summarize/stream_log")
})

document.querySelector("#input-chat").addEventListener("keydown", (e) => {
    if(e.keyCode === 13) { 
        sendRequest(uri = "/chain/summarize/stream_log")
    }
})

document.querySelector("#btn-fold-out").addEventListener("click", (e) => {
    const sidebar = document.querySelector(".sidebar");
    sidebar.style.width = "260px"

    e.target.style.display = "none"
})
let pdftext = ''
// 上传文件并处理逻辑
document.querySelector("#input-file-send").addEventListener("click",  async() => {
  console.log("开始上传文件");
  const fileInput = document.getElementById("pdf-file");
  const analysisType = document.getElementById("analysis-type").value;
  const resultLog = document.getElementById("res-log");

  if (fileInput.files.length === 0) {
    alert("请先选择一个 PDF 文件");
    return;
  }

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  formData.append("type", analysisType);

  const response = await fetch("http://127.0.0.1:8000/paperuploader", {
    method: "POST",
    body: formData
  });
  // 以json形式获得结果
  const result = await response.json();
  // 取得里面的content
  pdftext = result.content;
  console.log("文件上传成功，内容:", pdftext.slice(0, 100));
});


//let uri = "/chain/summarize/stream_log"
// 处理非结构性输出
function sendRequest(uri) {
    let origintext = document.querySelector("#input-chat").value;
    let text = origintext + pdftext;

    //console.log("发送请求，内容:", text);
    const resLog = document.querySelector("#res-log")
    const selfMsg = document.createElement("div");
    selfMsg.innerText = origintext;
    //console.log("innerText:", selfMsg.innerText);

    //selfMsg.innerHTML = marked.parse(origintext);
    selfMsg.className = "self-msg"
    resLog.appendChild(selfMsg);

    const llmMsg = document.createElement("div");
    const llmMsg_P = document.createElement("p");
    llmMsg.className = "llm-msg"
    llmMsg.appendChild(llmMsg_P);
    resLog.appendChild(llmMsg);
    
    fetch(`http://127.0.0.1:8000${uri}`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            input: { input: text },
            config: {}
        }),
    }).then(response => {
        if (!response.ok) throw new Error(`HTTP错误! 状态码: ${response.status}`);
        console.log("请求成功，开始处理流数据");
        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        const res = llmMsg_P;
        
        function processSSE(chunk) {
            const events = chunk.split('\n\n');
            //console.log('处理SSE事件:', events);
            events.forEach(event => {
                if (!event.trim()) return;
                
                const dataMatch = event.match(/data: (\{[\s\S]*\})/);
                
                if (dataMatch) {
                    try {
                        const jsonData = JSON.parse(dataMatch[1]);
                        if (jsonData.ops) {
                            jsonData.ops.forEach(op => {
                                if (op.path === '/logs/qwen-turbo/streamed_output_str/-') {
                                    res.innerHTML += marked.parse(op.value);
                                }
                                else if (op.path === '/final_output' && op.value?.content) {
                                    res.innerHTML =marked.parse( op.value.content);
                                }
                                // 适配其他可能的路径
                                else if (op.path.endsWith('streamed_output_str/-')) {
                                    res.innerHTML += marked.parse(op.value);
                                }
                            });
                        }
                    } catch (e) {
                        console.error('JSON解析错误', e);
                        res.innerHTML += `<span class="error">解析错误: ${e.message}</span>`;
                    }
                }
            });
        }

        function read() {
            reader.read().then(({ done, value }) => {
                if (done) {
                    // 添加工具栏
                    const toolbar = document.createElement("div");
                    toolbar.className = "tool-bar";
                    toolbar.innerHTML = `
                        <span class="iconfont icon-fuzhi"></span>
                        <span class="iconfont icon-shuaxin"></span>
                        <span class="iconfont icon-cai"></span>
                    `;
                    llmMsg.appendChild(toolbar);
                    return;
                }
                
                const chunk = decoder.decode(value, { stream: true });
                processSSE(chunk);
                read();
            }).catch(handleStreamError);
        }
        
        function handleStreamError(error) {
            console.error('流错误', error);
            res.innerHTML += `<span class="error">流错误: ${error.message}</span>`;
        }
        
        read();
    }).catch(handleFetchError);
    
    function handleFetchError(error) {
        console.error('请求错误:', error);
        if (llmMsg_P.contains(loader)) {
            llmMsg_P.removeChild(loader);
        }
        llmMsg_P.innerHTML = `<span class="error">请求失败: ${error.message}</span>`;
    }
}

/*function sendRequest(){
    const text = document.querySelector("#input-chat").value
    const data = {
        input: {
            input: text,
        },
        config: {}
    }; 

    const resLog = document.querySelector("#res-log")
    const selfMsg = document.createElement("div");
    selfMsg.innerText = text;
    selfMsg.className = "self-msg"
    resLog.appendChild(selfMsg);

    const llmMsg = document.createElement("div");
    const llmMsg_P = document.createElement("p");
    llmMsg.className = "llm-msg"
    llmMsg.appendChild(llmMsg_P);
    resLog.appendChild(llmMsg);

    fetch(`http://127.0.0.1:8000${uri}`,{
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data),
    }).then(response => {
        if (response.ok) {
            const reader = response.body.getReader();
            const decoder = new TextDecoder("utf-8");
            const res = llmMsg_P;

            
            function read() {
                reader.read().then(({ done, value }) => {
                    if (done) {
                        console.log('Stream closed');
                        const llmMsg_toolbar = document.createElement("div");
                        llmMsg_toolbar.className = "tool-bar"
                        llmMsg_toolbar.innerHTML = `
                            <span class="iconfont icon-fuzhi"></span>
                            <span class="iconfont icon-shuaxin"></span>
                            <span class="iconfont icon-cai"></span>
                        `
                        llmMsg.appendChild(llmMsg_toolbar);
                        return;
                    }

                    const chunk = decoder.decode(value, { stream: true });
                    // console.log(1000,chunk.split('\r\n'))
                    chunk.split('\r\n').forEach(eventString => {
                        // console.log(1000,eventString);
                        if (eventString && eventString.startsWith('data: ')) {
                            // console.log(2000,eventString);
                            const str = eventString.substring("data: ".length);
                            const data = JSON.parse(str)
                            // console.log(3000,data);
                            for(const item of data.ops){
                                if(item.op === "add" && item.path === "logs/ChatTongyi/streamed_output_str/-"){
                                    // console.log(item.value)
                                    res.innerHTML += item.value;  
                                }
                                if(item.op === "add" && item.path === "/logs/PydanticToolsParser/final_output"){
                                    if(String(item.value.output) !== "null" && String(item.value.output) !== "undefined"){
                                        // console.log(JSON.stringify(item.value.output, null, 2))
                                        res.innerHTML = `<pre>${JSON.stringify(item.value.output, null, 2)}</pre>`;
                                        break;
                                    }
                                }
                            }
                        }
                    });
                    

                    read();
                }).catch(error => {
                    console.error('Stream error', error);
                });
            }

            read();
        } else {
            console.error('Network response was not ok.');
        }
    }).catch(error => {
        console.error('Fetch error:', error);
    });    
}

const selectLLM = document.getElementById('selectLLM');
selectLLM.addEventListener('change', function() {
    const selectedOption = this.options[this.selectedIndex];
    console.log('Selected option:', selectedOption.value);
    uri = `/chain/${selectedOption.value}/stream_log`
});*/