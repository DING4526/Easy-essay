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

        key_sections = parser.extract_key_sections(parsed_data)
        print(f"[ANALYZE] Extracted key sections: {list(key_sections.keys())}")

        def _format_sections(sections: Dict[str, str]) -> str:
            return "\n\n".join([f"## {k.capitalize()}\n{v.strip()}" for k, v in sections.items() if v.strip()])

        key_sections_text = _format_sections(key_sections)
        ai_service = AIService()

        paper.title = parsed_data.get('title', paper.original_filename)
        paper.authors = parsed_data.get('authors', '')
        paper.abstract = parsed_data.get('abstract', '')

        print(f"[ANALYZE] Title: {paper.title}, Authors: {paper.authors}")

        if paper.abstract and paper.title:
            paper.summary = ai_service.generate_summary(paper.abstract, paper.title)
            print(f"[ANALYZE] Summary generated")
        else:
            paper.summary = f"这是一篇关于{paper.title}的学术论文。"

        if key_sections_text:
            paper.key_content = ai_service.extract_key_content(key_sections_text, paper.title)
            print(f"[ANALYZE] Key content extracted")
        else:
            paper.key_content = "关键内容提取功能需要更完整的论文结构。"

        if paper.abstract:
            paper.translation = ai_service.translate_text(paper.abstract)
            print(f"[ANALYZE] Abstract translated")
        else:
            paper.translation = "未找到摘要内容进行翻译。"

        full_text = parsed_data.get('full_text', '')
        if full_text:
            paper.terminology = ai_service.explain_terminology(full_text[:2000])
            print(f"[ANALYZE] Terminology explained")
        else:
            paper.terminology = "术语解释功能需要更完整的文本内容。"

        paper.research_context = ai_service.analyze_research_context(
            paper.title, paper.abstract, paper.key_content
        )
        print(f"[ANALYZE] Research context analyzed")

        # rag 构建
        if full_text:
            ai_service.setup_rag(full_text, paper.id)
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
        result = ai_service.answer_question(request_data.question, paper_id)
        print(f"[CHAT] LLM answer completed")

        chat_session = ChatSession(
            paper_id=paper_id,
            user_id=request_data.user_id,
            question=request_data.question,
            answer=result['answer']
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
            answer=result['answer'],
            timestamp=chat_session.timestamp,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


# ========== 聊天历史记录 ==========
@router.get("/{paper_id}/chat/history", response_model=List[ChatResponse])
async def get_chat_history(paper_id: int, user_id: int = 1, db: Session = Depends(get_db_session)):
    chats = db.query(ChatSession).filter_by(paper_id=paper_id, user_id=user_id).order_by(ChatSession.timestamp.asc()).all()
    return [ChatResponse.model_validate(chat) for chat in chats]
