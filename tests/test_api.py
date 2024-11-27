import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import os

from glowtalk.api import app, get_db
from glowtalk.models import Base, OriginalWork, Speaker, SpeakerModel
from glowtalk.database import init_db

# Create in-memory database for testing
TEST_DB_URL = "sqlite:///:memory:"

@pytest.fixture
def test_cwd(tmp_path):
    """Create and change to a temporary working directory with references subdirectory"""
    original_cwd = os.getcwd()
    references_dir = tmp_path / "references"
    references_dir.mkdir()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(original_cwd)

@pytest.fixture
def db_session(test_cwd):
    """Create a fresh database for each test"""
    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)

@pytest.fixture
def client(db_session):
    """Create a test client with the test database"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)

@pytest.fixture
def sample_work(db_session):
    """Create a sample work for testing"""
    work = OriginalWork(url="https://glowfic.com/posts/123")
    db_session.add(work)
    db_session.commit()
    return work

@pytest.fixture
def sample_speaker(db_session, test_cwd):
    """Create a sample speaker with a mock reference file"""
    ref_path = test_cwd / "references" / "test_speaker.wav"
    ref_path.write_bytes(b"fake audio data")

    speaker = Speaker.get_or_create(
        db_session,
        "test_speaker",
        SpeakerModel.XTTS_v2
    )
    db_session.add(speaker)
    db_session.commit()
    return speaker

def test_get_work(client, sample_work):
    """Test getting an existing work"""
    response = client.get(f"/api/works/{sample_work.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["url"] == sample_work.url

def test_get_nonexistent_work(client):
    """Test getting a work that doesn't exist"""
    response = client.get("/api/works/99999")
    assert response.status_code == 404

def test_create_audiobook(client, sample_work, sample_speaker):
    """Test creating a new audiobook"""
    response = client.post(
        f"/api/works/{sample_work.id}/audiobooks",
        json={
            "description": "Test audiobook",
            "default_speaker_id": sample_speaker.id
        }
    )
    assert response.status_code == 200
    data = response.json()

    # Check all fields
    assert data["description"] == "Test audiobook"
    assert data["default_speaker_id"] == sample_speaker.id
    assert data["original_work_id"] == sample_work.id
    assert data["forked_from_id"] is None
    assert "id" in data
    assert "created_at" in data

def test_create_audiobook_minimal(client, sample_work):
    """Test creating an audiobook with minimal data"""
    response = client.post(
        f"/api/works/{sample_work.id}/audiobooks",
        json={}  # No data required
    )
    assert response.status_code == 200
    data = response.json()
    assert data["description"] is None
    assert data["default_speaker_id"] is None
    assert data["original_work_id"] == sample_work.id

def test_create_audiobook_invalid_speaker(client, sample_work):
    """Test creating an audiobook with non-existent speaker"""
    response = client.post(
        f"/api/works/{sample_work.id}/audiobooks",
        json={
            "description": "Test audiobook",
            "default_speaker_id": 99999  # Non-existent speaker
        }
    )
    assert response.status_code == 404
    assert "Speaker not found" in response.json()["detail"]

def test_create_audiobook_invalid_work(client):
    """Test creating an audiobook for non-existent work"""
    response = client.post(
        f"/api/works/99999/audiobooks",
        json={"description": "Test audiobook"}
    )
    assert response.status_code == 404
    assert "Work not found" in response.json()["detail"]

def test_set_character_voice(client, sample_work, sample_speaker, db_session):
    """Test setting a character voice for an audiobook"""
    # First create an audiobook
    response = client.post(
        f"/api/works/{sample_work.id}/audiobooks",
        json={"description": "Test audiobook"}
    )
    audiobook_id = response.json()["id"]

    # Then set a character voice
    response = client.post(
        f"/api/audiobooks/{audiobook_id}/character-voices",
        json={
            "character_name": "Test Character",
            "speaker_id": sample_speaker.id
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["character_name"] == "Test Character"
    assert data["speaker_id"] == sample_speaker.id

def test_queue_status(client):
    """Test getting queue status"""
    response = client.get("/api/queue/status")
    assert response.status_code == 200
    data = response.json()
    assert "pending" in data
    assert "in_progress" in data
    assert "completed" in data
    assert "failed" in data

def test_generate_audiobook(client, sample_work, sample_speaker, db_session):
    """Test starting audiobook generation"""
    # Create an audiobook
    response = client.post(
        f"/api/works/{sample_work.id}/audiobooks",
        json={
            "description": "Test audiobook",
            "default_speaker_id": sample_speaker.id
        }
    )
    audiobook_id = response.json()["id"]

    # Start generation
    response = client.post(f"/api/audiobooks/{audiobook_id}/generate")
    assert response.status_code == 200
    data = response.json()
    assert "queued_items" in data

def test_create_speaker(client, test_cwd):
    """Test creating a new speaker"""

    response = client.post(
        "/api/speakers",
        data={
            "name": "test_speaker",
            "model": "XTTS_v2"
        },
        files={
            "reference_audio": ("new_speaker.wav", b"test audio data")
        }
    )

    if response.status_code != 200:
        print(response.json())
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["model"] == "tts_models/multilingual/multi-dataset/xtts_v2"

def test_create_speaker_missing_reference(client):
    """Test creating a speaker with missing reference file"""
    response = client.post(
        "/api/speakers",
        json={
            "name": "nonexistent_speaker",
            "model": "XTTS_v2"
        }
    )
    assert response.status_code == 422
    assert "Field required" in response.text
