import re
from src.core.schemas import SourceFile, CodeChunk
from src.core.config import get_settings
from src.core.utils import stable_hash, estimate_tokens

class CodeChunker:
    """Splits SourceFile records into retrieval-sized CodeChunk records."""

    def __init__(self):
        self.settings = get_settings()
        self.chunk_size = self.settings.chunk_size
        self.chunk_overlap = self.settings.chunk_overlap

    def _split_by_structure(self, text: str, language: str) -> list:
        """Split text into preliminary segments based on file language."""
        if language == "markdown":
            pattern = r'(?=^#{1,3}\s)'
            segments = re.split(pattern, text, flags=re.MULTILINE)

        elif language == "python":
            pattern = r'(?=^(?:def |class )\w)'
            segments = re.split(pattern, text, flags=re.MULTILINE)

        else:
            paragraphs = re.split(r'\n\s*\n', text)
            segments = paragraphs

        return [s for s in segments if s.strip()]

    def _merge_segments(self, segments: list) -> list:
        """Merge small segments into chunks that stay within the size limit."""
        chunks = []
        current = ""

        for segment in segments:
            if estimate_tokens(current + segment) <= self.chunk_size:
                current += segment
            else:
                if current.strip():
                    chunks.append(current)
                current = segment

        if current.strip():
            chunks.append(current)

        return chunks

    def _chunk_single_file(self, source_file: SourceFile) -> list:
        """Generate CodeChunk objects for one file."""
        segments = self._split_by_structure(
            source_file.content,
            source_file.language
        )
        merged = self._merge_segments(segments)

        chunks = []
        for index, chunk_text in enumerate(merged):
            lines_before = source_file.content[:
                source_file.content.find(chunk_text)].count("\n")
            start_line = lines_before + 1
            end_line = start_line + chunk_text.count("\n")

            chunk = CodeChunk(
                chunk_id=stable_hash(source_file.path + str(index)),
                file_path=source_file.path,
                chunk_index=index,
                text=chunk_text,
                start_line=start_line,
                end_line=end_line,
                token_estimate=estimate_tokens(chunk_text)
            )
            chunks.append(chunk)

        return chunks

    def chunk_files(self, files: list) -> list:
        """Chunk all files in the repository and return all CodeChunks."""
        all_chunks = []

        for source_file in files:
            try:
                file_chunks = self._chunk_single_file(source_file)
                all_chunks.extend(file_chunks)
            except Exception as e:
                print(f"Warning: could not chunk {source_file.path}: {e}")
                continue

        return all_chunks



