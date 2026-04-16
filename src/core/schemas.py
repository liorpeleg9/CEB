from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

@dataclass
class SourceFile:
    """Represents one file read from the repository."""
    path: str
    language: str
    content: str
    size_bytes: int
    sha256: str

@dataclass
class CodeChunk:
    """Represents one chunk of code ready for embedding and retrieval."""
    chunk_id: str
    file_path: str
    chunk_index: int
    text: str
    start_line: int
    end_line: int
    token_estimate: int

@dataclass
class RetrievalResult:
    """Represents one search result returned by the retriever."""
    chunk_id: str
    file_path: str
    score: float
    preview_text: str
    chunk_text: str

@dataclass
class ChatTurn:
    """Represents one question-answer exchange saved to the database."""
    question: str
    answer: str
    sources: List[str]
    created_at: datetime = field(default_factory=datetime.now)

@dataclass
class IndexSummary:
    """Represents the outcome of one indexing run."""
    repo_id: int
    file_count: int
    chunk_count: int
    duration_seconds: float
    warnings: List[str] = field(default_factory=list)

