from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from datetime import datetime
from models.db import Base

class Paper(Base):
    __tablename__ = "papers"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    upload_time = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    # 分析结果
    title = Column(Text)
    authors = Column(Text)
    abstract = Column(Text)
    summary = Column(Text)
    key_content = Column(Text)
    translation = Column(Text)
    terminology = Column(Text)
    research_context = Column(Text)

    processing_status = Column(String(50), default='uploaded')


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(Integer, ForeignKey('papers.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)