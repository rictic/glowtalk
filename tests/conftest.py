import pytest
import uvicorn
import multiprocessing
import socket
import httpx
from unittest.mock import MagicMock
from glowtalk import models, glowfic_scraper
import os
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from glowtalk.api import app, get_db
from glowtalk.models import Base
from fastapi.testclient import TestClient
import signal

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
<div class="content-header">
    <span id="post-title">Test Post Title</span>
</div>
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
        return glowfic_scraper.create_from_glowfic(url, db, soup)

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

def find_free_port():
    """Find and return a free port number"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port

def run_server(host="127.0.0.1", port=None):
    """Run the FastAPI app using uvicorn in a separate process"""
    if port is None:
        port = find_free_port()
    uvicorn.run(app, host=host, port=port)

@pytest.fixture
async def test_server():
    """Fixture that starts a test server and yields an AsyncClient"""
    port = find_free_port()
    server_process = multiprocessing.Process(target=run_server, kwargs={"port": port})
    server_process.start()

    # Add a signal handler to kill the server if we get a keyboard interrupt
    def signal_handler(signal, frame):
        server_process.terminate()
        raise KeyboardInterrupt
    signal.signal(signal.SIGINT, signal_handler)

    client = httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}")

    # Try to hit the /api/ok over and over until the server is ready
    while True:
        try:
            await client.get("/api/ok")
            break
        except Exception:
            continue

    yield client

    # Cleanup
    await client.aclose()
    server_process.terminate()



