import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import os
from pathlib import Path

from glowtalk import models, worker
from glowtalk.worker import Worker
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

SECOND_MOCK_GLOWFIC_HTML = """
<div class="post-container">
    <div class="post-post">
        <div class="post-info-text">
            <div class="post-character">Joey</div>
            <div class="post-screenname">JoeyScreen</div>
            <div class="post-author">AuthorThree</div>
        </div>
        <div class="post-content">
            <p>This is Joey speaking.</p>
        </div>
    </div>
</div>
"""

@pytest.fixture
def mock_speaker_model(monkeypatch):
    """Mock the speaker model to avoid actual TTS generation"""
    class MockSpeakerModel:
        def __init__(self, model: models.SpeakerModel):
            self.model = model

        def speak(self, text, speaker_wav, output_path):
            output_path.write_bytes( b"generated audio data for " + bytes(text, "utf8"))
            return output_path

    monkeypatch.setattr("glowtalk.speak.Speaker", MockSpeakerModel)

@pytest.fixture
def mock_glowfic_scraper(monkeypatch):
    """Mock the glowfic scraper to return our test data"""
    from bs4 import BeautifulSoup

    def mock_scrape(post_id, db):
        if post_id == 1234:
            soup = BeautifulSoup(MOCK_GLOWFIC_HTML, 'html.parser')
        else:
            soup = BeautifulSoup(SECOND_MOCK_GLOWFIC_HTML, 'html.parser')
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

@pytest.fixture
def mock_combine_wav_to_mp3(monkeypatch):
    """Mock the combine_wav_to_mp3 function to verify WAV file contents"""
    call_count = 0

    def mock_combine(wav_files, output_mp3_path):
        nonlocal call_count
        call_count += 1
        # Read all WAV files and concatenate their contents
        combined_contents = b""
        for wav_file in wav_files:
            with open(wav_file, "rb") as f:
                combined_contents += f.read()

        # Write the combined contents to the output MP3 file
        with open(output_mp3_path, "wb") as f:
            f.write(combined_contents)

    monkeypatch.setattr("glowtalk.convert.combine_wav_to_mp3", mock_combine)
    return lambda: call_count

def test_full_workflow(client, db_session, mock_glowfic_scraper, mock_speaker_model,
                      mock_combine_wav_to_mp3, test_cwd):
    # 1. Create two speakers (Alice and Bob)
    for speaker_name in ["alice", "bob"]:
        response = client.post(
            "/api/speakers",
            data={
                "name": speaker_name,
                "model": "XTTS_v2"
            },
            files={
                "reference_audio": (f"{speaker_name}.wav", b"test audio data for " + bytes(speaker_name, "utf8"))
            }
        )
        assert response.status_code == 200

    alice_speaker_id = 1
    bob_speaker_id = 2

    # 2. Create a new work (this will trigger our mocked scraper)
    response = client.post(
        "/api/works/scrape_glowfic",
        json={"post_id": 1234}
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

    expected_queue_status = {
        "pending": 0,
        "in_progress": 0,
        "completed": 0,
        "failed": 0
    }
    queue_status = client.get("/api/queue/status").json()
    assert queue_status == expected_queue_status

    # 5. Start generation

    response = client.post(f"/api/audiobooks/{audiobook_id}/generate")
    assert response.status_code == 200
    queued_items = response.json()["queued_items"]
    assert queued_items == 6  # Two Alice sentences, two Bob sentences, and two post announcements / descriptions.

    expected_queue_status["pending"] = queued_items
    queue_status = client.get("/api/queue/status").json()
    assert queue_status == expected_queue_status

    # Starting generation is idempotent
    response = client.post(f"/api/audiobooks/{audiobook_id}/generate")
    assert response.status_code == 200
    queued_items = response.json()["queued_items"]
    assert queued_items == 0
    queue_status = client.get("/api/queue/status").json()
    assert queue_status == expected_queue_status

    worker_id = "test_worker"
    worker = Worker(client, verbose=False, idle_threshold_seconds=5)

    while True:
        response = client.post("/api/queue/take", json={"worker_id": worker_id, "version": 1})
        if response.status_code != 200:
            print(response.text)
        assert response.status_code == 200
        item = response.json()
        if item is None:
            break
        expected_queue_status["in_progress"] += 1
        expected_queue_status["pending"] -= 1
        assert expected_queue_status == client.get("/api/queue/status").json()

        worker.work_one_item(item)
        expected_queue_status["completed"] += 1
        expected_queue_status["in_progress"] -= 1
        assert expected_queue_status == client.get("/api/queue/status").json()


    # MISSING API: We need an API to get audiobook status/details
    # For now, query the database directly
    performances = db_session.query(VoicePerformance).all()
    assert len(performances) == 6

    # Verify Alice's line used Alice's voice
    alice_performances = [p for p in performances if "Alice" in p.content_piece.part.character]
    assert [ap.speaker_id for ap in alice_performances] == [alice_speaker_id] * 3
    assert [ap.content_piece.part.character for ap in alice_performances] == ["Alice"] * 3
    assert [ap.content_piece.text for ap in alice_performances] == ["Alice (AliceScreen) (by AuthorOne):", "Hello there!", "This is Alice speaking."]

    # Verify Bob's line used Bob's voice
    bob_performances = [p for p in performances if "Bob" in p.content_piece.part.character]
    assert [bp.speaker_id for bp in bob_performances] == [bob_speaker_id] * 3
    assert [bp.content_piece.part.character for bp in bob_performances] == ["Bob"] * 3
    assert [bp.content_piece.text for bp in bob_performances] == ["Bob (BobScreen) (by AuthorTwo):", "Hi Alice!", "This is Bob."]

    # MISSING API: We need an API to get the final audio files/manifest
    # This would be useful for actually playing back the audiobook
    response = client.get(f"/api/audiobooks/{audiobook_id}/wav_files")
    assert response.status_code == 200
    wav_files = response.json()["files"]
    assert len(wav_files) == 6
    wav_file_contents = [
        client.get(f"/api/generated_wav_files/{wav_file_hash}").read()
        for wav_file_hash in wav_files
    ]
    assert wav_file_contents == [
        b"generated audio data for Alice (AliceScreen) (by AuthorOne):",
        b"generated audio data for Hello there!",
        b"generated audio data for This is Alice speaking.",
        b"generated audio data for Bob (BobScreen) (by AuthorTwo):",
        b"generated audio data for Hi Alice!",
        b"generated audio data for This is Bob."
    ]

    assert mock_combine_wav_to_mp3() == 0
    response = client.get(f"/api/audiobooks/{audiobook_id}/mp3")
    assert response.status_code == 200
    mp3_file = response.content
    assert mp3_file == b"".join(wav_file_contents)
    assert mock_combine_wav_to_mp3() == 1

    # get it again, but it shouldn't call convert again
    response = client.get(f"/api/audiobooks/{audiobook_id}/mp3")
    assert response.status_code == 200
    mp3_file = response.content
    assert mp3_file == b"".join(wav_file_contents)
    assert mock_combine_wav_to_mp3() == 1 # was cached

    # but a POST request forces a new generation
    response = client.post(f"/api/audiobooks/{audiobook_id}/mp3")
    assert response.status_code == 200
    mp3_file = response.content
    assert mp3_file == b"".join(wav_file_contents)
    assert mock_combine_wav_to_mp3() == 2

    response = client.post(f"/api/works/scrape_glowfic", json={"post_id": 5678})
    assert response.status_code == 200
    second_work_id = response.json()["id"]

    response = client.post(f"/api/works/{second_work_id}/audiobooks", json={"description": "Test audiobook 2", "default_speaker_id": alice_speaker_id})
    assert response.status_code == 200
    second_audiobook_id = response.json()["id"]
    response = client.post(f"/api/audiobooks/{second_audiobook_id}/generate")
    assert response.status_code == 200
    queued_items = response.json()["queued_items"]
    assert queued_items == 2  # Just one sentence and the suffix.

    expected_queue_status["pending"] += queued_items
    queue_status = client.get("/api/queue/status").json()
    assert queue_status == expected_queue_status

    # Request regenerations for several new takes on a content piece
    # get a voiced content piece
    content_piece = db_session.query(models.ContentPiece).filter(models.ContentPiece.should_voice == True).first()
    for i in range(3):
        assert content_piece is not None
        response = client.post(f"/api/content_pieces/{content_piece.id}/voice", json={"audiobook_id": audiobook_id})
        assert response.status_code == 200
        expected_queue_status["pending"] += 1
        queue_status = client.get("/api/queue/status").json()
        assert queue_status == expected_queue_status

    # Verify that taking an item from the queue gets the higher priority individual generation requests

    response = client.post("/api/queue/take", json={"worker_id": worker_id, "version": 1})
    assert response.status_code == 200
    item = response.json()
    assert item is not None
    assert "Alice" in item["text"] # Alice, not Joey
    expected_queue_status["in_progress"] += 1
    expected_queue_status["pending"] -= 1
    queue_status = client.get("/api/queue/status").json()
    assert queue_status == expected_queue_status

    # Finish the work item
    response = client.post(f"/api/queue/{item['id']}/complete/{worker_id}", files={"generated_audio": (f"{item['text']}.wav", b"updated generated audio for text: " + bytes(item["text"], "utf8"))})
    assert response.status_code == 200
    expected_queue_status["completed"] += 1
    expected_queue_status["in_progress"] -= 1
    queue_status = client.get("/api/queue/status").json()
    assert queue_status == expected_queue_status

    # Verify that the content piece has been updated with the new audio file
    response = client.get(f"/api/audiobooks/{audiobook_id}/wav_files")
    assert response.status_code == 200
    wav_files = response.json()["files"]
    assert len(wav_files) == 6
    wav_file_contents = [
        client.get(f"/api/generated_wav_files/{wav_file_hash}").read()
        for wav_file_hash in wav_files
    ]
    assert wav_file_contents == [
        b"updated generated audio for text: Alice (AliceScreen) (by AuthorOne):",
        b"generated audio data for Hello there!",
        b"generated audio data for This is Alice speaking.",
        b"generated audio data for Bob (BobScreen) (by AuthorTwo):",
        b"generated audio data for Hi Alice!",
        b"generated audio data for This is Bob."
    ]
