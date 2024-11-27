import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import os
from pathlib import Path

from glowtalk import models
from glowtalk.api import app, get_db
from glowtalk.models import Base, Speaker, SpeakerModel, WorkQueue, VoicePerformance
from glowtalk.glowfic_scraper import create_from_glowfic

# Mock data for our fake glowfic scraper
MOCK_GLOWFIC_HTML = """
<div class="post-container">
    <div class="post-post">
        <div class="post-info-text">
            <div class="post-character">Alice</div>
            <div class="post-screenname">AliceScreen</div>
            <div class="post-author">AuthorOne</div>
        </div>
        <div class="post-content">
            <p>Hello there! This is Alice speaking.</p>
        </div>
    </div>
    <div class="post-reply">
        <div class="post-info-text">
            <div class="post-character">Bob</div>
            <div class="post-screenname">BobScreen</div>
            <div class="post-author">AuthorTwo</div>
        </div>
        <div class="post-content">
            <p>Hi Alice! This is Bob.</p>
        </div>
    </div>
</div>
"""

@pytest.fixture
def mock_speaker_model(monkeypatch):
    """Mock the speaker model to avoid actual TTS generation"""
    class MockSpeakerModel:
        def speak(self, text, reference_path):
            # Create a fake audio file
            output_path = Path("output") / f"{hash(text)}.wav"
            output_path.parent.mkdir(exist_ok=True)
            output_path.write_bytes(b"fake audio data")
            return output_path

    monkeypatch.setattr("glowtalk.models._speaker_model", MockSpeakerModel())

@pytest.fixture
def mock_glowfic_scraper(monkeypatch):
    """Mock the glowfic scraper to return our test data"""
    from bs4 import BeautifulSoup

    def mock_scrape(post_id, db):
        soup = BeautifulSoup(MOCK_GLOWFIC_HTML, 'html.parser')
        url = f"https://glowfic.com/posts/{post_id}"
        return create_from_glowfic(url, db, soup)

    monkeypatch.setattr("glowtalk.glowfic_scraper.scrape_post", mock_scrape)

@pytest.fixture
def test_cwd(tmp_path):
    """Create and change to a temporary working directory"""
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
        "sqlite:///:memory:",
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

def test_full_workflow(client, db_session, mock_glowfic_scraper, mock_speaker_model, test_cwd):
    # 1. Create two speakers (Alice and Bob)
    for speaker_name in ["alice", "bob"]:
        response = client.post(
            "/api/speakers",
            data={
                "name": speaker_name,
                "model": "XTTS_v2"
            },
            files={
                "reference_audio": (f"{speaker_name}.wav", b"test audio data")
            }
        )
        assert response.status_code == 200

    alice_speaker_id = 1
    bob_speaker_id = 2

    # 2. Create a new work (this will trigger our mocked scraper)
    response = client.post(
        "/api/works/scrape_glowfic",
        json={"post_id": 12345}
    )
    assert response.status_code == 200
    work_id = response.json()["id"]
    # Read the database to verify that the work was created
    work = db_session.get(models.OriginalWork, work_id)
    assert work is not None
    # It should have two Parts
    assert len(work.parts) == 2

    # 3. Create an audiobook with Alice as the default speaker
    response = client.post(
        f"/api/works/{work_id}/audiobooks",
        json={
            "description": "Test audiobook",
            "default_speaker_id": alice_speaker_id
        }
    )
    assert response.status_code == 200
    audiobook_id = response.json()["id"]

    # 4. Assign Bob's voice to Bob's character and Alice's to Alice's
    response = client.post(
        f"/api/audiobooks/{audiobook_id}/character-voices",
        json={
            "character_name": "Alice",
            "speaker_id": alice_speaker_id
        }
    )
    assert response.status_code == 200

    response = client.post(
        f"/api/audiobooks/{audiobook_id}/character-voices",
        json={
            "character_name": "Bob",
            "speaker_id": bob_speaker_id
        }
    )
    assert response.status_code == 200

    # 5. Start generation
    response = client.post(f"/api/audiobooks/{audiobook_id}/generate")
    assert response.status_code == 200
    queued_items = response.json()["queued_items"]
    assert queued_items == 4  # Two Alice sentences, two Bob sentences

    # MISSING API: We need a worker API endpoint that processes queue items
    # For now, we'll simulate a worker directly
    worker_id = "test_worker"
    while True:
        item = WorkQueue.assign_work_item(db_session, worker_id)
        if item is None:
            break
        content_piece = item.content_piece
        speaker = content_piece.get_speaker_for_audiobook(db_session, item.audiobook)
        performance = speaker.generate_voice_performance(db_session, content_piece, item.audiobook)
        item.complete_work_item(db_session, worker_id, performance)


    # 6. Verify the results
    # Check queue status
    response = client.get("/api/queue/status")
    assert response.status_code == 200
    status = response.json()
    assert status["completed"] == 4
    assert status["pending"] == 0
    assert status["in_progress"] == 0
    assert status["failed"] == 0

    # MISSING API: We need an API to get audiobook status/details
    # For now, query the database directly
    performances = db_session.query(VoicePerformance).all()
    assert len(performances) == 4

    # Verify Alice's line used Alice's voice
    alice_performances = [p for p in performances if "Alice" in p.content_piece.part.character]
    assert [ap.speaker_id for ap in alice_performances] == [alice_speaker_id] * 2
    assert [ap.content_piece.part.character for ap in alice_performances] == ["Alice"] * 2
    assert [ap.content_piece.text for ap in alice_performances] == ["Hello there!", "This is Alice speaking."]

    # Verify Bob's line used Bob's voice
    bob_performances = [p for p in performances if "Bob" in p.content_piece.part.character]
    assert [bp.speaker_id for bp in bob_performances] == [bob_speaker_id] * 2
    assert [bp.content_piece.part.character for bp in bob_performances] == ["Bob"] * 2
    assert [bp.content_piece.text for bp in bob_performances] == ["Hi Alice!", "This is Bob."]

    # MISSING API: We need an API to get the final audio files/manifest
    # This would be useful for actually playing back the audiobook
