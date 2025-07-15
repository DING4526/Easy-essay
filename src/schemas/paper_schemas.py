from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class PaperResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_path: str
    upload_time: datetime
    user_id: int

    title: Optional[str]
    authors: Optional[str]
    abstract: Optional[str]
    summary: Optional[str]
    key_content: Optional[str]
    translation: Optional[str]
    terminology: Optional[str]
    research_context: Optional[str]
    processing_status: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class ParsedDataSummary(BaseModel):
    sections_count: int
    tables_count: int
    images_count: int
    formulas_count: int
    references_count: int


class PaperAnalysisResult(BaseModel):
    message: str
    paper: PaperResponse
    parsed_data: ParsedDataSummary

