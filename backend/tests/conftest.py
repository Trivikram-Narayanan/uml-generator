"""
tests/conftest.py  –  shared fixtures for all tests
"""
import os, pytest, asyncio
os.environ["TESTING"]    = "true"
os.environ["DB_PATH"]    = ":memory:"   # in-memory SQLite for tests
os.environ["LLM_BACKEND"]= "mock"       # never call a real model in tests
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.models import Base
from db.database import get_db
from api.main import app

# ── In-memory test DB ─────────────────────────────────────────────────────────

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession  = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True, scope="session")
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session():
    async with TestSession() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(db_session):
    """HTTP client with DB dependency overridden to use test session."""
    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ── Auth helpers ──────────────────────────────────────────────────────────────

@pytest.fixture
async def auth_client(client):
    """Client pre-authenticated as a test user."""
    await client.post("/api/auth/register", json={
        "email": "test@example.com",
        "username": "testuser",
        "password": "testpassword123",
    })
    resp = await client.post("/api/auth/login",
        data={"username": "test@example.com", "password": "testpassword123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token = resp.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


@pytest.fixture
async def second_auth_client(client):
    """A second authenticated user for isolation tests."""
    await client.post("/api/auth/register", json={
        "email": "other@example.com",
        "username": "otheruser",
        "password": "otherpassword123",
    })
    resp = await client.post("/api/auth/login",
        data={"username": "other@example.com", "password": "otherpassword123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token = resp.json()["access_token"]
    from httpx import AsyncClient, ASGITransport
    ac = AsyncClient(transport=ASGITransport(app=app), base_url="http://test",
                     headers={"Authorization": f"Bearer {token}"})
    yield ac
    await ac.aclose()
