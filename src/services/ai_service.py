import os
import re
import json
from typing import List, Dict, Any
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.chains import RetrievalQA
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.prompts import ChatPromptTemplate
from langchain.schema import Document

from configs import DATA_DIR


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

    # def _simple_prompt(self, user_msg: str, system_msg: str = "") -> str:
    #     prompt = ChatPromptTemplate.from_messages([
    #         ("system", system_msg),
    #         ("user", user_msg)
    #     ])
    #     messages = prompt.format_messages()
    #     # print("[LLM] format prompt:", messages)
    #     print(f"[LLM] answer: {self.llm.invoke(messages).content[:20]}...")
    #     return self.llm.invoke(messages).content

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

    def safe_prompt_from_rag(self, result_text: str) -> str:
        prompt_template = """
        请结合以下RAG检索的内容，作为你的专业背景知识，回答用户的问题，提供一个学术权威又通俗易懂的解释：

        {}
        """
        return prompt_template.format(self.safe_text(result_text))

    def answer_question(self, question: str, paper_id: int = None) -> Dict[str, Any]:
        """基于RAG回答问题"""
        if not self.qa_chain:
            if paper_id and not self.load_rag(paper_id):
                return {
                    "answer": "抱歉，无法加载论文的知识库，请先分析论文。",
                    "sources": []
                }

        if not self.qa_chain:
            return {
                "answer": "抱歉，知识库未初始化，请先上传并分析论文。",
                "sources": []
            }

        # 打开并读取 JSON 文件、

        try:
            result = self.qa_chain.invoke({"query": question})
            prompt = self.safe_prompt_from_rag(result["result"])
            answer = self._simple_prompt(prompt)

            sources = []
            if "source_documents" in result:
                sources = [doc.page_content[:200] + "..." for doc in result["source_documents"]]

            return {
                "answer": answer,
                "sources": sources
            }
        except Exception as e:
            return {
                "answer": f"回答问题时出错：{str(e)}",
                "sources": []
            }


