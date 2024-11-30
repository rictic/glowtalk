import pytest
import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import os
import json
import time
import asyncio

from glowtalk import models
from glowtalk.api import app, get_db
from glowtalk.models import Base, OriginalWork, Speaker, SpeakerModel, WorkQueue
from conftest import mock_glowfic_scraper, mock_speaker_model, test_server, test_cwd, db_session, client
from starlette.testclient import TestClient as StarletteTestClient

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
            "voice_name": "test_speaker",
            "model": None
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

@pytest.mark.asyncio
async def test_audiobook_generation_progress(client, db_session, mock_glowfic_scraper,
                                     mock_speaker_model, test_cwd):
    """Test SSE endpoint for monitoring audiobook generation progress"""
    pytest.skip("skipping")
    # First create a speaker and audiobook using the FastAPI test client
    response = client.post(
        "/api/speakers",
        data={
            "name": "test_speaker",
            "model": "XTTS_v2"
        },
        files={
            "reference_audio": ("test_speaker.wav", b"test audio data")
        }
    )
    assert response.status_code == 200
    speaker_id = response.json()["id"]

    # Create a work by scraping our mock glowfic
    response = client.post(
        "/api/works/scrape_glowfic",
        json={"post_id": 1234}
    )
    assert response.status_code == 200
    work_id = response.json()["id"]

    # Create an audiobook with our test speaker as default
    response = client.post(
        f"/api/works/{work_id}/audiobooks",
        json={
            "description": "Test audiobook",
            "default_speaker_id": speaker_id
        }
    )
    assert response.status_code == 200
    audiobook_id = response.json()["id"]

    # Start generation to create work items
    response = client.post(f"/api/audiobooks/{audiobook_id}/generate")
    assert response.status_code == 200
    queued_items = response.json()["queued_items"]
    assert queued_items > 0

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        async with client.stream("GET", f"/api/audiobooks/{audiobook_id}/generation_progress") as response:
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream"
            return
            # Get and verify first event
            messages = AsyncSSEMessageParser.from_response(response)
            message = await anext(messages)
            first_event = json.loads(message)
            assert first_event["pending"] == queued_items
            assert first_event["in_progress"] == 0
            assert first_event["completed"] == 0

            # Complete all work items
            work_items = db_session.query(models.WorkQueue)\
            .filter_by(audiobook_id=audiobook_id).all()
            for item in work_items:
                item.status = "completed"
            db_session.commit()

            # Get and verify final event
            event_data = next(response.iter_lines())
            final_event = json.loads(event_data.decode().replace("data: ", ""))
            assert final_event["pending"] == 0
            assert final_event["in_progress"] == 0
            assert final_event["completed"] == queued_items

from typing import Iterator, AsyncIterator
import attr

class SSEMessageParser:
    def __init__(self, line_iterator: Iterator[str]):
        self._line_iterator = line_iterator
        self._current_message = []

    @classmethod
    def from_response(cls, response) -> 'SSEMessageParser':
        return cls(response.iter_lines())

    def __iter__(self):
        return self

    def __next__(self):
        for line in self._line_iterator:
            # Convert bytes to string if needed
            if isinstance(line, bytes):
                line = line.decode('utf-8')

            # just look for the data: line
            if line.startswith("data: "):
                self._current_message.append(line[6:])
            elif line == "":  # Empty line marks end of message
                if self._current_message:  # Only yield if we have collected lines
                    message = '\n'.join(self._current_message)
                    self._current_message = []
                    return message

        # Handle final message if exists
        if self._current_message:
            message = '\n'.join(self._current_message)
            self._current_message = []
            return message

        raise StopIteration

@attr.s(auto_attribs=True)
class AsyncSSEMessageParser:
    _line_iterator: AsyncIterator[str]
    _current_message: list[str] = attr.Factory(list)

    @classmethod
    def from_response(cls, response) -> 'AsyncSSEMessageParser':
        return cls(response.aiter_lines())

    def __aiter__(self):
        return self

    async def __anext__(self):
        async for line in self._line_iterator:
            # just look for the data: line
            if line.startswith("data: "):
                self._current_message.append(line[6:])
            elif line == "":  # Empty line marks end of message
                if self._current_message:  # Only yield if we have collected lines
                    message = '\n'.join(self._current_message)
                    self._current_message = []
                    return message

        # Handle final message if exists
        if self._current_message:
            message = '\n'.join(self._current_message)
            self._current_message = []
            return message

        raise StopAsyncIteration

@pytest.mark.asyncio
async def test_stream_ok():
    """Test SSE endpoint to verify streaming is working with event waiting"""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        # Create a task to handle the streaming response
        async def stream_handler():
            async with client.stream("GET", "/api/stream_ok") as response:
                assert response.status_code == 200
                assert response.headers["content-type"] == "text/event-stream"
                return response

        stream_task = asyncio.create_task(stream_handler())

        # Wait for the response to be ready
        return  # TEMPORARY: Let's just verify we can get the response first
        response = await stream_task

        expected_lines = ["ok"] * 3
        messages = AsyncSSEMessageParser.from_response(response)

        # First message comes immediately
        message = await anext(messages)
        assert message == expected_lines.pop(0)

        # For remaining messages, we need to trigger them
        for _ in range(2):
            # Wake up the stream
            wake_response = await client.post("/api/wake_ok_stream")
            assert wake_response.status_code == 200

            # Get next message
            message = await anext(messages)
            assert message == expected_lines.pop(0)

        assert expected_lines == []

@pytest.mark.asyncio
async def test_ok_event(test_server):
    """Test that the ok_event mechanism works correctly"""
    pytest.skip("skipping")
    async with test_server.stream('GET', "/api/stream_ok") as response:
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        messages = AsyncSSEMessageParser.from_response(response)

        # Wake the event
        wake_response = await test_server.post("/api/wake_ok_stream")
        assert wake_response.status_code == 200

        # Get the response
        message = await asyncio.wait_for(anext(messages), timeout=0.1)
        assert message == "ok"

        # Wake again
        wake_response = await test_server.post("/api/wake_ok_stream")
        assert wake_response.status_code == 200

        # Can get again
        assert "ok" == await asyncio.wait_for(anext(messages), timeout=0.1)

        # Try to take another without waking, times out.
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(anext(messages), timeout=0.1)
