import sqlite3
import json
import numpy as np
from pathlib import Path
from src.core.schemas import SourceFile, CodeChunk, ChatTurn
from src.core.config import get_settings

class DatabaseManager:
    """Owns all SQLite read and write operations for the application."""

    def __init__(self):
        self.settings = get_settings()
        self.db_path = Path(self.settings.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize_schema()

    def initialize_schema(self):
        """Create all database tables if they don't already exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS repositories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    normalized_path TEXT UNIQUE NOT NULL,
                    status TEXT NOT NULL,
                    last_indexed_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    repo_id INTEGER NOT NULL,
                    relative_path TEXT NOT NULL,
                    language TEXT NOT NULL,
                    sha256 TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    repo_id INTEGER NOT NULL,
                    file_id INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    start_line INTEGER NOT NULL,
                    end_line INTEGER NOT NULL,
                    text TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS embeddings (
                    chunk_id INTEGER PRIMARY KEY,
                    vector_blob BLOB NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    repo_id INTEGER NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    source_paths_json TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def upsert_repository(self, repo_path: str, status: str) -> int:
        """Create or update a repository record and return its id."""
        with sqlite3.connect(self.db_path) as conn:
            existing = conn.execute(
                "SELECT id FROM repositories WHERE normalized_path = ?",
                (repo_path,)
            ).fetchone()

            if existing:
                conn.execute(
                    "UPDATE repositories SET status = ?, last_indexed_at = datetime('now') WHERE id = ?",
                    (status, existing[0])
                )
                return existing[0]
            else:
                cursor = conn.execute(
                    "INSERT INTO repositories (normalized_path, status, last_indexed_at) VALUES (?, ?, datetime('now'))",
                    (repo_path, status)
                )
                conn.commit()
                return cursor.lastrowid

    def replace_repository_index(self, repo_id: int, files: list,
                                 chunks: list, embeddings: list) -> None:
        """Replace all indexed content for a repository in one transaction."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM embeddings WHERE chunk_id IN "
                         "(SELECT id FROM chunks WHERE repo_id = ?)", (repo_id,))
            conn.execute("DELETE FROM chunks WHERE repo_id = ?", (repo_id,))
            conn.execute("DELETE FROM files WHERE repo_id = ?", (repo_id,))

            file_id_map = {}
            for source_file in files:
                cursor = conn.execute(
                    "INSERT INTO files (repo_id, relative_path, language, sha256) "
                    "VALUES (?, ?, ?, ?)",
                    (repo_id, source_file.path, source_file.language, source_file.sha256)
                )
                file_id_map[source_file.path] = cursor.lastrowid

            chunk_ids = []
            for chunk in chunks:
                file_id = file_id_map.get(chunk.file_path, 0)
                cursor = conn.execute(
                    "INSERT INTO chunks (repo_id, file_id, chunk_index, "
                    "start_line, end_line, text) VALUES (?, ?, ?, ?, ?, ?)",
                    (repo_id, file_id, chunk.chunk_index,
                     chunk.start_line, chunk.end_line, chunk.text)
                )
                chunk_ids.append(cursor.lastrowid)

            for chunk_id, vector in zip(chunk_ids, embeddings):
                vector_blob = np.array(vector, dtype=np.float32).tobytes()
                conn.execute(
                    "INSERT INTO embeddings (chunk_id, vector_blob) VALUES (?, ?)",
                    (chunk_id, vector_blob)
                )

            conn.commit()

    def fetch_embeddings(self, repo_id: int) -> list:
        """Load all chunk ids and their vectors for a repository."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT c.id, e.vector_blob "
                "FROM chunks c "
                "JOIN embeddings e ON c.id = e.chunk_id "
                "WHERE c.repo_id = ?",
                (repo_id,)
            ).fetchall()

        results = []
        for chunk_id, vector_blob in rows:
            vector = np.frombuffer(vector_blob, dtype=np.float32).tolist()
            results.append((chunk_id, vector))
        return results

    def fetch_chunks(self, repo_id: int, chunk_ids: list) -> list:
        """Load full chunk objects for a list of chunk ids."""
        if not chunk_ids:
            return []

        placeholders = ",".join("?" * len(chunk_ids))
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                f"SELECT id, file_id, chunk_index, start_line, end_line, text "
                f"FROM chunks "
                f"WHERE repo_id = ? AND id IN ({placeholders})",
                (repo_id, *chunk_ids)
            ).fetchall()

        chunks = []
        for row in rows:
            chunk = CodeChunk(
                chunk_id=str(row[0]),
                file_path=str(row[1]),
                chunk_index=row[2],
                text=row[5],
                start_line=row[3],
                end_line=row[4],
                token_estimate=len(row[5]) // 4
            )

    def save_chat_turn(self, repo_id: int, turn: ChatTurn) -> None:
                """Persist one question-answer exchange to the database."""
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute(
                        "INSERT INTO chat_turns "
                        "(repo_id, question, answer, source_paths_json, created_at) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (
                            repo_id,
                            turn.question,
                            turn.answer,
                            json.dumps(turn.sources),
                            turn.created_at.isoformat()
                        )
                    )
                    conn.commit()

    def fetch_chat_history(self, repo_id: int, limit: int = 20) -> list:
        """Load the most recent chat turns for a repository."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT question, answer, source_paths_json, created_at "
                "FROM chat_turns "
                "WHERE repo_id = ? "
                "ORDER BY created_at DESC "
                "LIMIT ?",
                (repo_id, limit)
            ).fetchall()

        turns = []
        for row in rows:
            turn = ChatTurn(
                question=row[0],
                answer=row[1],
                sources=json.loads(row[2]) if row[2] else [],
                created_at=row[3]
            )
            turns.append(turn)

        return list(reversed(turns))

    def clear_repository(self, repo_id: int) -> None:
        """Delete all indexed data and chat history for a repository."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM embeddings WHERE chunk_id IN "
                "(SELECT id FROM chunks WHERE repo_id = ?)",
                (repo_id,)
            )
            conn.execute(
                "DELETE FROM chunks WHERE repo_id = ?",
                (repo_id,)
            )
            conn.execute(
                "DELETE FROM files WHERE repo_id = ?",
                (repo_id,)
            )
            conn.execute(
                "DELETE FROM chat_turns WHERE repo_id = ?",
                (repo_id,)
            )
            conn.execute(
                "UPDATE repositories SET status = 'reset', "
                "last_indexed_at = NULL WHERE id = ?",
                (repo_id,)
            )
            conn.commit()

