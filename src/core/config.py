import os
from dotenv import load_dotenv

# Load the .env file so our API key becomes available
load_dotenv()

class Settings:
    """Central configuration for the entire application."""

    def __init__(self):
        # OpenAI
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.model_name = "gpt-4o-mini"
        self.embedding_model = "text-embedding-3-small"

        # Chunking
        self.chunk_size = 512
        self.chunk_overlap = 64
        self.max_file_size_bytes = 1_000_000

        # Retrieval
        self.top_k = 5

        # Database
        self.db_path = "data/app.db"

        # Supported file types
        self.supported_extensions = {
            ".py", ".js", ".ts", ".jsx", ".tsx",
            ".java", ".cpp", ".c", ".h",
            ".md", ".txt", ".yaml", ".yml", ".json"
        }

        # Directories to skip
        self.ignored_dirs = {
            ".venv", "venv", "node_modules",
            "__pycache__", ".git", ".idea"
        }

    def validate(self):
        """Check that critical settings are present before the app starts."""
        if not self.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is missing. "
                "Please add it to your .env file."
            )
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                "chunk_overlap must be smaller than chunk_size."
            )

def get_settings() -> Settings:
    """Create, validate, and return the Settings object."""
    settings = Settings()
    settings.validate()
    return settings