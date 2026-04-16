import os
from pathlib import Path
from src.core.schemas import SourceFile
from src.core.config import get_settings
from src.core.utils import stable_hash, estimate_tokens

class CodeFileLoader:
    """Walks a repository and reads supported files into SourceFile records."""

    def __init__(self):
        self.settings = get_settings()

    def _detect_language(self, path: Path) -> str:
        """Map a file extension to a normalized language label."""
        extension_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".h": "c",
            ".md": "markdown",
            ".txt": "text",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".json": "json",
        }
        return extension_map.get(path.suffix.lower(), "text")

    def _should_skip(self, path: Path) -> bool:
        """Return True if this file should be ignored."""
        for ignored in self.settings.ignored_dirs:
            if ignored in path.parts:
                return True

        if path.suffix.lower() not in self.settings.supported_extensions:
            return True

        try:
            if path.stat().st_size > self.settings.max_file_size_bytes:
                return True
        except OSError:
            return True

        return False

    def _read_text(self, path: Path) -> str | None:
        """Read a file's content safely, returning None if unreadable."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            if not content.strip():
                return None
            return content
        except (UnicodeDecodeError, OSError, PermissionError):
            return None

    def scan_repository(self, repo_path: Path) -> list:
        """Walk the repository and return all readable files as SourceFile records."""
        source_files = []
        repo_path = Path(repo_path)

        for root, dirs, files in os.walk(repo_path):
            root_path = Path(root)

            dirs[:] = [
                d for d in dirs
                if d not in self.settings.ignored_dirs
            ]

            for filename in files:
                file_path = root_path / filename

                if self._should_skip(file_path):
                    continue

                content = self._read_text(file_path)
                if content is None:
                    continue

                relative_path = str(file_path.relative_to(repo_path))
                language = self._detect_language(file_path)
                file_hash = stable_hash(content)

                source_file = SourceFile(
                    path=relative_path,
                    language=language,
                    content=content,
                    size_bytes=len(content.encode("utf-8")),
                    sha256=file_hash
                )
                source_files.append(source_file)

        return source_files

