import os
import sys
import tempfile
from pathlib import Path

import pytest

_tmp = tempfile.mkdtemp(prefix="agentforge-test-")
os.environ.update(
    {
        "DATABASE_URL": f"sqlite+aiosqlite:///{_tmp}/test.db",
        "SECRET_KEY": "test-secret-key-for-agentforge-0123456789abcdef",
        "DEFAULT_PROVIDER": "mock",
        "DEFAULT_MODEL": "mock-smart",
        "SCHEDULER_ENABLED": "false",
        "RATE_LIMIT_AUTH_PER_MINUTE": "40",
        "RATE_LIMIT_GLOBAL_PER_MINUTE": "100000",
        "RATE_LIMIT_RUNS_PER_MINUTE": "1000",
        "MAX_CONCURRENT_RUNS_PER_ORG": "50",
    }
)
for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY", "TAVILY_API_KEY", "BRAVE_API_KEY"):
    os.environ[k] = ""
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.engine.tools import builtin
    from app.main import app

    async def fake_search(query: str, n: int):
        return (
            [
                {"title": "FastAPI release notes", "url": "https://fastapi.tiangolo.com/release-notes/", "snippet": f"Latest FastAPI changes about {query}"},
                {"title": "Example article", "url": "https://example.com/article", "snippet": "Second result snippet"},
            ][:n],
            "fake",
        )

    builtin._duckduckgo = fake_search  # deterministic search in tests
    with TestClient(app) as c:
        yield c
