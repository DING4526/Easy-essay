import os
import re
import json
from typing import List, Dict, Any

import requests
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.chains import RetrievalQA
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.prompts import ChatPromptTemplate
from langchain.schema import Document
from langgraph.graph import StateGraph,END

from configs import DATA_DIR

import time#用于访问时间限制
from typing import List, Dict, Any, TypedDict, Annotated, Literal,Optional
from operator import itemgetter

# --- LangChain 新增依赖 ---
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.tools import tool, Tool
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# 导入 Paper 模型，以便访问其属性
from models.paper import Paper


class S2State(TypedDict):
    title: str
    s2_id: str | None
    references: List[Dict]
    citations: List[Dict]
    final_result: str | Dict


class AIService:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('DASHSCOPE_API_KEY')
        self.llm = ChatTongyi(
            name="qwen-turbo",
            streaming=False,
            api_key=self.api_key
        )
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        # self.embeddings = OpenAIEmbeddings()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )
        self.vectorstore = None
        self.qa_chain = None
        self.rag_search_tool = self._get_rag_search_tool()
        self.generate_mindmap_mermaid = self._get_generate_mindmap_mermaid_tool()
        self.generate_flowchart_mermaid = self._get_generate_flowchart_mermaid_tool()

        #查看被引用文献基本信息
        # 我们不再从环境变量中读取S2_API_KEY，强制使用无Key模式
        # S2 API 配置
        self.s2_api_base = "https://api.semanticscholar.org/graph/v1"

        # --- 新增: Agent 相关变量 ---
        self.agent_executor = None

    def _simple_prompt(self, user_msg: str, system_msg: str = "") -> str:
        messages = []
        if system_msg:
            messages.append({"role": "system", "content": system_msg})
        messages.append({"role": "user", "content": user_msg})

        print(f"[LLM] answer: {self.llm.invoke(messages).content[:20]}...")
        return self.llm.invoke(messages).content

    def setup_rag(self, paper_content: str, paper_id: int):
        """设置RAG系统"""
        try:
            # 分割文档
            texts = self.text_splitter.split_text(paper_content)
            documents = [Document(page_content=text) for text in texts]
            
            # 创建向量存储
            persist_directory = os.path.join(DATA_DIR, "chroma_db", f"paper_{paper_id}")
            self.vectorstore = Chroma.from_documents(
                documents=documents,
                embedding=self.embeddings,
                persist_directory=persist_directory
            )
            
            # 创建QA链
            self.qa_chain = RetrievalQA.from_chain_type(
                llm=self.llm,
                chain_type="stuff",
                retriever=self.vectorstore.as_retriever(search_kwargs={"k": 3}),
                return_source_documents=True
            )
            
            return True
        except Exception as e:
            print(f"Error setting up RAG: {str(e)}")
            return False
    
    def load_rag(self, paper_id: int):
        """加载已存在的RAG系统"""
        try:
            persist_directory = os.path.join(DATA_DIR, "chroma_db", f"paper_{paper_id}")
            if os.path.exists(persist_directory):
                self.vectorstore = Chroma(
                    persist_directory=persist_directory,
                    embedding_function=self.embeddings
                )
                
                self.qa_chain = RetrievalQA.from_chain_type(
                    llm=self.llm,
                    chain_type="stuff",
                    retriever=self.vectorstore.as_retriever(search_kwargs={"k": 3}),
                    return_source_documents=True
                )

                return True
            return False
        except Exception as e:
            print(f"Error loading RAG: {str(e)}")
            return False
    
    def generate_summary(self, abstract: str, title: str) -> str:
        """生成简明摘要"""
        prompt = f"""
        请为以下学术论文生成一个简明的摘要，用一句话或一小段话通俗地解释这篇论文在做什么：

        论文标题：{title}
        论文摘要：{abstract}

        要求：
        1. 用通俗易懂的语言
        2. 突出论文的核心贡献
        3. 控制在50字以内
        """
        
        return self._simple_prompt(prompt)
    
    def extract_key_content(self, key_sections: dict, title: str) -> str:
        """提取关键内容"""
        introduction_text = key_sections.get("introduction", "not found introduction")
        method_text = key_sections.get("method", "not found method")
        experiments_text = key_sections.get("experiments", "not found experiments")
        conclusion_text = key_sections.get("conclusion", "not found conclusion")
        prompt = f"""
        请基于以下论文内容，提取并总结关键信息：

        论文标题：{title}
        
        论文主要章节内容：
        <introduction部分>: {introduction_text}
        <method部分>: {method_text}
        <experiments部分>: {experiments_text}
        <conclusion部分>: {conclusion_text}

        请按以下格式总结：
        1. 研究问题：
        2. 研究目标：
        3. 主要方法：
        4. 实验设计：
        5. 主要优点和贡献：

        每项用1-2句话概括。
        """
        
        return self._simple_prompt(prompt)
    
    def translate_text(self, text: str) -> str:
        """翻译文本"""
        prompt = f"""
        请将以下英文学术论文内容翻译成简体中文，保持学术性和准确性：

        {text}

        翻译要求：
        1. 保持原文的学术风格
        2. 专业术语要准确
        3. 语言要流畅自然
        """
        
        return self._simple_prompt(prompt)
    
    def explain_terminology(self, text: str) -> str:
        """解释术语"""
        prompt = f"""
        请从以下论文内容中识别关键术语，并提供通俗易懂的解释：

        {text}

        要求：
        1. 识别5-10个关键术语
        2. 每个术语提供解释
        3. 解释要通俗易懂
        4. 按以下格式输出：
           术语名称：解释内容
        """
        
        return self._simple_prompt(prompt)
    
    def analyze_research_context(self, title: str, abstract: str, key_content: str, references: str) -> str:
        """分析研究脉络"""
        prompt = f"""
        基于以下论文信息，请分析其研究脉络和背景：

        论文标题：{title}
        摘要：{abstract}
        关键内容：{key_content}
        参考文献：{references}

        请从以下角度分析：
        1. 研究领域和方向
        2. 相关的经典研究和论文
        3. 该研究在学术发展中的位置
        4. 可能的后续研究方向

        请提供结构化的分析结果。
        """
        
        return self._simple_prompt(prompt)


    def safe_text(self, text:str):
        if not isinstance(text, str):
            return text

        # 转义反斜杠（避免 \beta 等）
        text = text.replace('\\', '\\\\')

        # 清理非法或残缺变量占位符（如 t-1）
        text = re.sub(r'\{[^}]*\}', '[变量]', text)  # 替换 f-string 风格的占位符

        # 去除非 ascii 控制字符（防止编码错误）
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', text)

        return text

    def safe_prompt_from_rag(self, query_text:str, result_text: str) -> str:
        prompt_template = """
        【用户的问题】
        {}
        【你需要做的】
        请结合以下RAG检索的内容，作为你的专业背景知识，回答用户的问题，提供一个学术权威又通俗易懂的解释：{}
        """
        return prompt_template.format(query_text, self.safe_text(result_text))

    # def answer_question(self, question: str, paper_id: int = None) -> Dict[str, Any]:
    #     """基于RAG回答问题"""
    #     if not self.qa_chain:
    #         if paper_id and not self.load_rag(paper_id):
    #             return {
    #                 "answer": "抱歉，无法加载论文的知识库，请先分析论文。",
    #                 "sources": []
    #             }
    #
    #     if not self.qa_chain:
    #         return {
    #             "answer": "抱歉，知识库未初始化，请先上传并分析论文。",
    #             "sources": []
    #         }
    #
    #     # 打开并读取 JSON 文件、
    #
    #     try:
    #         result = self.qa_chain.invoke({"query": question})
    #         prompt = self.safe_prompt_from_rag(result["result"])
    #         answer = self._simple_prompt(prompt)
    #
    #         sources = []
    #         if "source_documents" in result:
    #             sources = [doc.page_content[:200] + "..." for doc in result["source_documents"]]
    #
    #         return {
    #             "answer": answer,
    #             "sources": sources
    #         }
    #     except Exception as e:
    #         return {
    #             "answer": f"回答问题时出错：{str(e)}",
    #             "sources": []
    #         }

    def _get_rag_search_tool(self):
        @tool
        def rag_search(query: str) -> str:
            """
            当你需要回答关于论文具体细节的问题时，使用此工具。
            它会从论文全文中搜索并找到最相关的答案。
            输入应该是用户的原始问题或你需要查找的具体主题。
            """
            print(f"[AGENT_TOOL] Calling RAG Search Tool with query: '{query}'")
            if not self.qa_chain:
                return "RAG 知识库未加载。无法回答问题。"
            try:
                result = self.qa_chain.invoke({"query": query})
                print(f"[AGENT_TOOL] RAG Search Tool Result: '{result}'")
                prompt = self.safe_prompt_from_rag(query, result["result"])
                print(f"[AGENT_TOOL] Final Prompt: '{prompt}']")
                res = self.llm.invoke(prompt).content  # 直接调用 llm
                if isinstance(res, str):
                    return res
                elif isinstance(res, list):
                    return "\n".join([str(x) for x in res])
                else:
                    return str(res)
            except Exception as e:
                return f"RAG 搜索时出错: {str(e)}"

        return Tool.from_function(
            func=rag_search,
            name="rag_search_tool",
            description="从论文全文中搜索并回答具体问题，输入应为用户的自然语言问题。"
        )


    def _get_generate_mindmap_mermaid_tool(self):
        @tool
        def generate_mindmap_mermaid(topic: str, content: Optional[str] = None) -> str:
            """
            当用户要求生成思维导图（mindmap）时使用此工具。
            'topic' 参数是思维导图的中心主题。
            'content' 参数是可选的，用于生成导图的详细文本。如果未提供'content'，此工具将自动搜索相关内容。
            """
            print(f"[AGENT_TOOL] Calling Mindmap Tool for topic: '{topic}'")

            if content is None:
                print(f"Mindmap content not provided for topic '{topic}'. Performing RAG search.")
                content = self.rag_search_tool.invoke(topic)  # 直接调用另一个工具
                if (content is None) or ("未能找到" in content) or ("无法回答" in content):
                    return f"无法为主题 '{topic}' 生成思维导图，因为在论文中找不到相关内容。"

            prompt = f"""
            你是一个数据可视化专家。请根据以下内容，并且精炼概括出关键内容，控制文本长度，创建一个 Mermaid.js 格式的思维导图。
            思维导图应以 '{topic}' 为中心主题，并清晰地展示信息的层级结构。

            内容:
            ---
            {content}
            ---

            请严格按照 Mermaid mindmap 语法输出，不要包含任何其他解释或注释，直接给出代码。
            """
            if not self.llm:
                return "LLM 未初始化。"
            res = self.llm.invoke(prompt).content
            if isinstance(res, str):
                return res
            elif isinstance(res, list):
                return "\n".join([str(x) for x in res])
            else:
                return str(res)

        return Tool.from_function(
            func=generate_mindmap_mermaid,
            name="generate_mindmap_mermaid_tool",
            description="当用户要求生成思维导图（mindmap）时使用此工具。"
        )

    def _get_generate_flowchart_mermaid_tool(self):
        @tool
        def generate_flowchart_mermaid(topic: str, content: Optional[str] = None) -> str:
            """
            当用户要求生成流程图（flowchart）来描述流程或步骤时使用此工具。
            'topic' 参数是流程图的标题。
            'content' 参数是可选的，描述流程步骤的详细文本。如果未提供'content'，此工具将自动搜索相关内容。
            """
            print(f"[AGENT_TOOL] Calling Flowchart Tool for topic: '{topic}'")

            if content is None:
                print(f"Flowchart content not provided for topic '{topic}'. Performing RAG search.")
                content = self.rag_search_tool.invoke(topic)  # 直接调用另一个工具
                if (content is None) or ("未能找到" in content) or ("无法回答" in content):
                    return f"无法为主题 '{topic}' 生成流程图，因为在论文中找不到相关内容。"

            prompt = f"""
            你是一个流程图绘制专家。请根据以下描述的流程，并且精炼概括出关键内容，控制文本长度，创建一个 Mermaid.js 格式的自顶向下（TD）流程图。
            流程图标题应为 '{topic}'。

            流程描述内容:
            ---
            {content}
            ---

            请严格按照 Mermaid graph TD 语法输出，不要包含任何其他解释或注释，直接给出代码。
            """
            if not self.llm:
                return "LLM 未初始化。"
            res = self.llm.invoke(prompt).content
            if isinstance(res, str):
                return res
            elif isinstance(res, list):
                return "\n".join([str(x) for x in res])
            else:
                return str(res)

        return Tool.from_function(
            func=generate_flowchart_mermaid,
            name="generate_flowchart_mermaid_tool",
            description="当用户要求生成流程图（flowchart）时使用此工具。"
        )

    # --- 替换旧的 answer_question 方法 ---
    # def answer_question被agentic_answer 和 rag_search_tool 替代，使用agent继承rag和问答，以及其他工具调用
    # def agentic_answer(self, question: str, paper: Paper) -> Dict[str, Any]:
    #     """
    #     使用 Agent 来回答问题，可以调用工具或进行普通问答。
    #     """
    #     # 每次调用时都重新设置 Agent，确保使用了正确的论文上下文
    #     self.setup_agent(paper)
    #
    #     if not self.agent_executor:
    #         return {"answer": "Agent 未初始化，请稍后再试。"}
    #
    #     print(f"[AGENT_INVOKE] Invoking agent with question: '{question}'")
    #     response = self.agent_executor.invoke({"input": question})
    #     print(f"[AGENT_INVOKE] Get Response: '{response}'")
    #
    #     output = response.get('output', "抱歉，我无法处理您的请求。")
    #
    #     # 尝试解析输出是否为我们定义的 JSON 格式
    #     try:
    #         # 如果 LLM 按照指示返回了 JSON 字符串，这里会解析成功
    #         data = json.loads(output)
    #         if "diagram" in data:
    #             print("[AGENT_INVOKE] Detected diagram in response.")
    #             return data
    #     except json.JSONDecodeError:
    #         # 如果不是 JSON，说明是普通的文本回答
    #         print("[AGENT_INVOKE] Plain text response from agent.")
    #         return {"answer": output}
    #
    #     # 如果是 JSON 但格式不对，也作为普通文本返回
    #     return {"answer": output}

    def agentic_answer(self, question: str, paper: Paper) -> Dict[str, Any]:
        """
        使用 Agent 来回答问题，返回统一格式：
        {
            "answer": "...",
            "diagram": { ... } 或 None
        }
        """
        self.setup_agent(paper)

        if not self.agent_executor:
            return {
                "answer": "Agent 未初始化，请稍后再试。",
                "diagram": None
            }

        print(f"[AGENT_INVOKE] Invoking agent with question: '{question}'")
        response = self.agent_executor.invoke({"input": question})
        print(f"[AGENT_INVOKE] Get Raw response: '{response}'")

        output = response.get("output", "").strip()

        try:
            # 尝试解析 JSON 格式
            data = json.loads(output)

            # 容错处理：字段不全时补齐
            return {
                "answer": data.get("answer", "").strip(),
                "diagram": data.get("diagram", None)
            }

        except json.JSONDecodeError:
            # 非 JSON 格式：为普通文本，仍包装成统一结构
            print("[AGENT_INVOKE] Non-JSON plain text response.")
            return {
                "answer": output,
                "diagram": None
            }


    # def setup_agent(self, paper: Paper):
    #     """
    #     根据指定的论文，配置一个具备工具调用能力的 Agent。
    #     """
    #     print(f"[AGENT] Setting up agent for paper_id: {paper.id}")
    #
    #     if not self.load_rag(paper.id):
    #         print(f"[AGENT_WARNING] Could not load RAG for paper {paper.id}. RAG tool will be unavailable.")
    #
    #     # 工具链
    #     tools = [self.rag_search_tool, self.generate_mindmap_mermaid, self.generate_flowchart_mermaid]
    #
    #     paper_context = f"""
    #         # 论文核心信息 (概览)
    #         ## 标题: {paper.title}
    #         ## 摘要: {paper.summary}
    #         ## 关键内容总结:
    #         {paper.key_content}
    #         ## 研究脉络：
    #         {paper.research_context}
    #         """
    #
    #     # 这就是 Few-shot 示例。
    #     json_format_example = """{
    #     "diagram": {
    #         "type": "mermaid",
    #         "code": "mindmap\\n  root(论文关键内容)\\n    (研究问题)\\n      (研究目标)\\n    (主要方法)\\n    (实验设计)\\n    (主要贡献)",
    #         "title": "论文关键内容思维导图"
    #     },
    #     "answer": "这是为您生成的图表："
    # }"""
    #
    #     final_system_prompt_text = f"""
    # 你是一个顶级的、拥有自主规划能力的论文分析助手。你的任务是理解用户需求，并规划一系列工具调用来完成任务。
    #
    # # 你拥有的工具:
    # 1. `rag_search_tool(query: str)`: 从论文全文中搜索**具体细节**。
    # 2. `generate_mindmap_mermaid(topic: str, content: Optional[str])`: 创建**思维导图**。
    # 3. `generate_flowchart_mermaid(topic: str, content: Optional[str])`: 创建**流程图**。
    #
    # # 核心工作策略:
    # - **信息搜集**: 如果是普通问答不需要绘图，**必须**调用 `rag_search_tool` 获取信息进行回答。如果绘图所需的具体信息不在下面的【论文核心信息】中，你**必须**先调用 `rag_search_tool` 获取信息，再调用绘图工具。
    # - **最终输出**: 如果是普通问答，**没有要求绘制流程图和思维导图，不能调用了绘图工具**，直接返回文本。如果用户问题中**要求绘制流程图和思维导图**，你的最终回答**必须**是一个JSON字符串，不包含任何其他文字或解释。
    #
    # # 论文核心信息:
    # {paper_context}
    # """
    #
    #     # 创建一个包含指令和示例的完整消息列表
    #     prompt_messages = [
    #         SystemMessage(content=final_system_prompt_text),
    #         # --- Few-Shot 示例 ---
    #         HumanMessage(content="请给我画一个关于'XXX'的思维导图。"),  # 虚构的用户问题
    #         AIMessage(content=json_format_example),  # 告诉模型，对于绘图请求，应该返回这样的JSON
    #         # --- 真实的用户输入 ---
    #         ("user", "{input}"),
    #         ("placeholder", "{agent_scratchpad}"),
    #     ]
    #
    #     # 3. 创建 ChatPromptTemplate
    #     prompt_template = ChatPromptTemplate.from_messages(prompt_messages)
    #
    #     agent = create_tool_calling_agent(self.llm, tools, prompt_template)
    #     self.agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
    #     print(f"[AGENT] Agent for paper_id: {paper.id} is ready.")

    def setup_agent(self, paper: Paper):
        """
        根据指定的论文，配置一个具备工具调用能力的 Agent。
        """
        print(f"[AGENT] Setting up agent for paper_id: {paper.id}")

        if not self.load_rag(paper.id):
            print(f"[AGENT_WARNING] Could not load RAG for paper {paper.id}. RAG tool will be unavailable.")

        # 工具链
        tools = [self.rag_search_tool, self.generate_mindmap_mermaid, self.generate_flowchart_mermaid]

        paper_context = f"""
            # 论文核心信息
            ## 标题: {paper.title}
            ## 摘要: {paper.summary}
            ## 关键内容总结:
            {paper.key_content}
            ## 研究脉络：
            {paper.research_context}
            """

        # 这就是 Few-shot 示例。
        json_format_example = """{
        "diagram": {
            "type": "mermaid",
            "code": "mindmap\\n  root(论文关键内容)\\n    (研究问题)\\n      (研究目标)\\n    (主要方法)\\n    (实验设计)\\n    (主要贡献)",
            "title": "论文关键内容思维导图"
        },
        "answer": "这是为您生成的图表："
    }"""

        final_system_prompt_text = f"""
你是一个论文分析专家，具备自主规划和工具调用能力。

你可以使用以下工具：
- rag_search_tool：用于从论文全文中查找细节
- generate_mindmap_mermaid_tool：生成思维导图
- generate_flowchart_mermaid_tool：生成流程图

# 回答逻辑：
- 所有问题都先调用 rag_search_tool 获取背景知识。
- 如果用户要求生成图表（如“画流程图”、“思维导图”），你应基于 rag_search_tool 的结果调用图工具。
- **最终输出始终是 JSON 格式，包含以下字段：**

```json
{{
  "answer": "回答文本（可为空）",
  "diagram": {{
    "type": "mermaid",
    "title": "图标题",
    "code": "Mermaid代码"
  }} 或 null
}}

# 论文核心信息:
{paper_context}
"""

        prompt_messages = [
            SystemMessage(content=final_system_prompt_text),
            HumanMessage(content="请画一张XXX的流程图。"),
            AIMessage(content=json_format_example),
            ("user", "{input}"),
            ("placeholder", "{agent_scratchpad}")
        ]

        prompt_template = ChatPromptTemplate.from_messages(prompt_messages)
        agent = create_tool_calling_agent(self.llm, tools, prompt_template)

        self.agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
        print(f"[AGENT] Agent for paper_id: {paper.id} is ready.")



    # --- 新增：带重试机制的API请求器 ---
    def _make_s2_api_request(self, url: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        max_retries = 3
        initial_delay = 5  # 初始等待5秒
        for attempt in range(max_retries):
            try:
                response = requests.get(
                    url,
                    params=params,
                    headers={},  # 强制使用免费API
                    timeout=15  # 设置请求超时
                )
                response.raise_for_status()  # 对4xx/5xx错误抛出HTTPError
                return response.json()
            except requests.RequestException as e:
                if e.response is not None and e.response.status_code == 429:
                    wait_time = initial_delay * (2 ** attempt)  # 指数增加等待时间
                    print(f"[S2_API_HANDLER] Rate limit exceeded (429). Retrying in {wait_time} seconds... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    print(f"[S2_API_HANDLER] API request failed at {url}. Error: {e}")
                    if e.response:
                        print(f"[S2_API_HANDLER] Response content: {e.response.text}")
                    return None
        print(f"[S2_API_HANDLER] Failed to get a successful response from {url} after {max_retries} attempts.")
        return None

    def _search_paper(self, state: S2State) -> S2State:
        title = state['title']
        print(f"[S2_SEARCH] Searching for paper with title: {title}")
        url = f"{self.s2_api_base}/paper/search"
        params = {"query": title, "fields": "title", "limit": 1}
        data = self._make_s2_api_request(url, params)
        if data and data.get('total', 0) > 0 and data.get('data'):
            s2_id = data['data'][0]['paperId']
            found_title = data['data'][0]['title']
            print(f"[S2_SEARCH] Found a match. S2 ID: {s2_id}, Title: {found_title}")
            return {**state, "s2_id": s2_id}
        else:
            print(f"[S2_SEARCH] Paper not found on Semantic Scholar for title: '{title}'")
            return {**state, "s2_id": None}

    def _fetch_references_and_citations(self, state: S2State) -> S2State:
        s2_id = state['s2_id']
        fields = "title,publicationDate,citationCount"
        def fetch_data(endpoint: str) -> List[Dict]:
            url = f"{self.s2_api_base}/paper/{s2_id}/{endpoint}"
            params = {"fields": fields, "limit": 10} # 获取前10条
            print(f"[S2_FETCH] Calling API: {url}")
            response_data = self._make_s2_api_request(url, params)
            if response_data:
                data = response_data.get('data', [])
                print(f"[S2_FETCH] Successfully fetched {len(data)} items from '{endpoint}'.")
                return data
            return [] # 如果请求失败，返回空列表
        references_data = fetch_data("references")
        citations_data = fetch_data("citations")
        references = [item['citedPaper'] for item in references_data if item.get('citedPaper')]
        citations = [item['citingPaper'] for item in citations_data if item.get('citingPaper')]
        print(f"[S2_FETCH] Extracted {len(references)} references and {len(citations)} citations.")
        return {**state, "references": references, "citations": citations}
    def _compile_results(self, state: S2State) -> S2State:
        references = state.get("references", [])
        citations = state.get("citations", [])
        print(f"[S2_COMPILE] Compiling final result with {len(references)} references and {len(citations)} citations.")
        result = {
            "references": references,
            "citations": citations
        }
        return {**state, "final_result": json.dumps(result, ensure_ascii=False)}
    def _decide_to_fetch(self, state: S2State) -> str:
        if state.get('s2_id'):
            print("[S2_DECIDE] S2 ID found. Proceeding to fetch data.")
            return "fetch"
        else:
            print("[S2_DECIDE] S2 ID not found. Skipping fetch.")
            return "not_found"
    def _handle_not_found(self, state: S2State) -> S2State:
        print("[S2_NOT_FOUND] Finalizing process as paper was not found.")
        return {**state, "final_result": "在Semantic Scholar API无法查询到该论文"}
    def fetch_related_papers(self, title: str) -> Dict[str, Any]:
        workflow = StateGraph(S2State)
        workflow.add_node("search", self._search_paper)
        workflow.add_node("fetch", self._fetch_references_and_citations)
        workflow.add_node("compile", self._compile_results)
        workflow.add_node("not_found", self._handle_not_found)
        workflow.set_entry_point("search")
        workflow.add_conditional_edges(
            "search",
            self._decide_to_fetch,
            {"fetch": "fetch", "not_found": "not_found"}
        )
        workflow.add_edge("fetch", "compile")
        workflow.add_edge("compile", END)
        workflow.add_edge("not_found", END)
        graph = workflow.compile()
        initial_state = {"title": title, "s2_id": None, "references": [], "citations": [], "final_result": {}}
        print(f"[S2_WORKFLOW] Starting related papers workflow for title: '{title}'")
        final_state = graph.invoke(initial_state)
        print(f"[S2_WORKFLOW] Workflow completed.")
        return {
            "s2_id": final_state.get('s2_id'),
            "related_papers_json": final_state.get('final_result')
        }



