import hashlib
import os
from pathlib import Path

def normalize_repo_path(path_str: str) -> Path:
    """Convert a raw user-entered path into a clean absolute Path object."""
    path_str = path_str.strip().strip('"').strip("'")
    path = Path(path_str).expanduser().resolve()
    return path

def stable_hash(text: str) -> str:
    """Generate a deterministic hash string from any text input."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in a text string."""
    return len(text) // 4

def truncate_preview(text: str, max_chars: int = 220) -> str:
    """Create a short preview string for display in the UI."""
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."

