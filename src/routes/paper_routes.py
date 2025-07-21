import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Request
from sqlalchemy.orm import Session

from models.db import get_db_session
from models.paper import Paper, ChatSession
from services.pdf_parser_pro import PDFParser
from services.ai_service import AIService

from pydantic import BaseModel
from schemas.paper_schemas import *
from schemas.chat_schemas import *

from configs import DATA_DIR
from services.tools import *

router = APIRouter(prefix="/papers", tags=["papers"])

UPLOAD_FOLDER = os.path.join(DATA_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@router.get("/env-check")
def env_check():
    import sys
    import os
    return {
        "python_path": sys.executable,
        "env_path": os.environ.get("PATH"),
        "tesseract_path": os.environ.get("TESSDATA_PREFIX"),
    }


# ========== 上传论文 ==========
@router.post("/upload")
async def upload_paper(
    file: UploadFile = File(...),
    user_id: int = Form(1),
    db: Session = Depends(get_db_session),
):
    print(f"[UPLOAD] 用户 user_id={user_id} 上传文件 filename={file.filename}")
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Invalid file type")

    filename = f"{uuid.uuid4()}_{file.filename}"
    file_path = os.path.join(UPLOAD_FOLDER, filename)

    with open(file_path, "wb") as f:
        f.write(await file.read())

    paper = Paper(
        filename=filename,
        original_filename=file.filename,
        file_path=file_path,
        user_id=user_id,
        processing_status="uploaded"
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)

    print(f"[UPLOAD] 文件已保存到 file_path={paper.file_path}, paper_id={paper.id}")

    return {
        "message": "File uploaded successfully",
        "paper_id": paper.id,
        "filename": paper.original_filename
    }


# ========== 分析论文 ==========
@router.post("/{paper_id}/analyze", response_model=PaperAnalysisResult)
async def analyze_paper(paper_id: int, db: Session = Depends(get_db_session)):
    print(f"[ANALYZE] 开始分析论文 paper_id={paper_id}")
    paper = db.query(Paper).get(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    if paper.processing_status == 'processing':
        raise HTTPException(status_code=400, detail="Paper is already being processed")

    paper.processing_status = 'processing'
    db.commit()

    try:
        parser = PDFParser()
        parsed_data = parser.parse_pdf(paper.id, paper.file_path)
        print(f"[ANALYZE] PDF parse finished")

        ai_service = AIService()

        paper.title = parsed_data.get('title', paper.original_filename)
        paper.authors = ', '.join(parsed_data.get('authors', []))
        paper.abstract = parsed_data.get('abstract', '')

        print(f"[ANALYZE] 已保存 paper.title: {paper.title}")
        print(f"[ANALYZE] 已保存 paper.authors: {paper.authors}")
        print(f"[ANALYZE] 已保存 paper.abstract: {paper.abstract[:100]}...")

        if paper.abstract and paper.title:
            paper.summary = ai_service.generate_summary(paper.abstract, paper.title)
            print(f"[ANALYZE] 已生成并保存 paper.summary")
        else:
            paper.summary = f"这是一篇关于{paper.title}的学术论文。"

        key_sections = extract_core_sections(parsed_data.get('sections',[]))

        if key_sections:
            paper.key_content = ai_service.extract_key_content(key_sections, paper.title)
            print(f"[ANALYZE] 已生成并保存 paper.key_content")
        else:
            paper.key_content = "未提取到有效的key_sections"

        if paper.abstract:
            paper.translation = ai_service.translate_text(paper.abstract)
            print(f"[ANALYZE] 已完成摘要翻译（目前是demo版本）")
        else:
            paper.translation = "未提取到有效的摘要内容"

        full_text = parsed_data.get('full_text', '')
        if full_text:
            paper.terminology = ai_service.explain_terminology(full_text[:2000])
            print(f"[ANALYZE] 已生成术语解释")
        else:
            paper.terminology = "未提取到full_text文本内容。"

        paper_references = ', '.join(parsed_data.get('references', []))
        paper.research_context = ai_service.analyze_research_context(
            paper.title, paper.abstract, paper.key_content, paper_references
        )
        print(f"[ANALYZE] Research context analyzed")

        # --- 新增：调用Semantic Scholar服务 ---
        print(f"[ANALYZE] Fetching related papers from Semantic Scholar for title: {paper.title}")
        related_data = ai_service.fetch_related_papers(paper.title)
        paper.s2_id = related_data.get('s2_id')
        paper.related_papers_json = related_data.get('related_papers_json')
        print(f"[ANALYZE] Semantic Scholar data fetched. S2 ID: {paper.s2_id}")

        # rag 构建
        # 首先，先提取引用的文章
        references = extract_references_section(parsed_data)
        titles = []
        for title in references:
            title = extract_reference_title(title)
            titles.append(title)
            # print(f"Reference title: {title}")

        # 根据标题构建增强内容
        rag_chunks = build_rag_chunks_from_titles(titles)

        print(f"[ANALYZE] RAG chunks built: {len(rag_chunks)} items")
        print(f"[ANALYZE] RAG chunks[0]: {rag_chunks[0] if rag_chunks else 'No chunks available'}")

        # 拼接为一个整体string
        augmented_full_text = full_text + "\n\n" + "\n\n".join(rag_chunks)
        print(f"[RAG] augmented_full_text:\n{augmented_full_text}")

        if augmented_full_text:
            ai_service.setup_rag(augmented_full_text, paper.id)
            print(f"[ANALYZE] RAG setup completed")

        paper.processing_status = 'completed'
        db.commit()

        print(f"[ANALYZE] Paper {paper_id} analysis completed")

        return PaperAnalysisResult(
            message="Paper analysis completed",
            paper=PaperResponse.model_validate(paper),
            parsed_data=ParsedDataSummary(
                sections_count=len(parsed_data.get('sections', [])),
                tables_count=len(parsed_data.get('tables', [])),
                images_count=len(parsed_data.get('images', [])),
                formulas_count=len(parsed_data.get('formulas', [])),
                references_count=len(parsed_data.get('references', [])),
            )
        )

    except Exception as e:
        paper.processing_status = 'failed'
        db.commit()
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


# ========== 获取单篇论文 ==========
@router.get("/{paper_id}", response_model=PaperResponse)
async def get_paper(paper_id: int, db: Session = Depends(get_db_session)):
    paper = db.query(Paper).get(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return PaperResponse.model_validate(paper)


# ========== 获取论文列表 ==========
@router.get("/", response_model=List[PaperResponse])
async def get_papers(user_id: int = 1, db: Session = Depends(get_db_session)):
    papers = db.query(Paper).filter_by(user_id=user_id).order_by(Paper.upload_time.desc()).all()
    return [PaperResponse.model_validate(p) for p in papers]


# ========== 聊天问答 ==========
@router.post("/{paper_id}/chat", response_model=ChatResponse)
async def chat_with_paper(paper_id: int, request_data: QuestionRequest, db: Session = Depends(get_db_session)):
    print(f"[CHAT] user_id={request_data.user_id} asking: question='{request_data.question}' for paper_id={paper_id}")
    paper = db.query(Paper).get(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    ai_service = AIService()
    try:
        result_dict = ai_service.agentic_answer(request_data.question, paper)
        print(f"[CHAT] Agent result received: {result_dict}")
        print(f"[CHAT] LLM answer completed")

        # --- 将结果字典序列化为 JSON 字符串存入数据库 ---
        # 这样前端就能收到完整的结构化信息
        answer_content = json.dumps(result_dict, ensure_ascii=False)

        chat_session = ChatSession(
            paper_id=paper_id,
            user_id=request_data.user_id,
            question=request_data.question,
            # answer=result['answer']
            answer=answer_content
        )
        db.add(chat_session)
        db.commit()
        db.refresh(chat_session)

        print(f"[CHAT] Saved chat session id={chat_session.id}")

        return ChatResponse(
            id=chat_session.id,
            paper_id=paper_id,
            user_id=request_data.user_id,
            question=request_data.question,
            # answer=result['answer'],
            answer=answer_content,
            timestamp=chat_session.timestamp,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")

# ========== 聊天历史记录 ==========
@router.get("/{paper_id}/chat/history", response_model=List[ChatResponse])
async def get_chat_history(paper_id: int, user_id: int = 1, db: Session = Depends(get_db_session)):
    chats = db.query(ChatSession).filter_by(paper_id=paper_id, user_id=user_id).order_by(ChatSession.timestamp.asc()).all()
    return [ChatResponse.model_validate(chat) for chat in chats]
