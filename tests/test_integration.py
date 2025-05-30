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
from conftest import mock_glowfic_scraper, mock_speaker_model, test_cwd, db_session, client, mock_combine_wav_to_mp3


def test_speaker_creation_and_listing_and_models_api(client, db_session):
    # Test speaker models API
    response = client.get("/api/speaker_models")
    assert response.status_code == 200
    models_data = response.json()
    assert "tts_models/multilingual/multi-dataset/xtts_v2" in models_data
    assert "speecht5_tts" in models_data

    # Test listing speakers (should be empty initially)
    response = client.get("/api/speakers")
    assert response.status_code == 200
    assert response.json() == []

    # Create two speakers (Alice and Bob)
    created_speaker_ids = {}
    for speaker_name in ["alice", "bob"]:
        response = client.post(
            "/api/speakers",
            data={
                "name": speaker_name,
                "model": "XTTS_v2"  # Using a valid model from the API
            },
            files={
                "reference_audio": (f"{speaker_name}.wav", b"test audio data for " + bytes(speaker_name, "utf8"))
            }
        )
        assert response.status_code == 200
        speaker_data = response.json()
        assert speaker_data["name"] == speaker_name
        assert speaker_data["model_name"] == "tts_models/multilingual/multi-dataset/xtts_v2"
        created_speaker_ids[speaker_name] = speaker_data["id"]

    assert "alice" in created_speaker_ids
    assert "bob" in created_speaker_ids

    # Test listing speakers (should now have Alice and Bob)
    response = client.get("/api/speakers")
    assert response.status_code == 200
    speakers_list = response.json()
    assert len(speakers_list) == 2
    speaker_names_in_response = {s["name"] for s in speakers_list}
    assert "alice" in speaker_names_in_response
    assert "bob" in speaker_names_in_response
    # Verify IDs and model names
    for speaker_data in speakers_list:
        assert speaker_data["id"] == created_speaker_ids[speaker_data["name"]]
        assert speaker_data["model_name"] == "tts_models/multilingual/multi-dataset/xtts_v2"


def test_get_audiobook(client, db_session, mock_glowfic_scraper):
    # 1. Create a speaker
    speaker_name = "test_speaker_for_get_audiobook"
    speaker_response = client.post(
        "/api/speakers",
        data={"name": speaker_name, "model": "XTTS_v2"},
        files={"reference_audio": (f"{speaker_name}.wav", b"test audio data")}
    )
    assert speaker_response.status_code == 200
    speaker_id = speaker_response.json()["id"]

    # 2. Create a work (uses mock_glowfic_scraper)
    work_response = client.post("/api/works/scrape_glowfic", json={"post_id": 7890})
    assert work_response.status_code == 200
    work_id = work_response.json()["id"]
    assert work_response.json()["title"] == "Test Post Title" # From mock

    # 3. Create an audiobook for that work
    audiobook_description = "Audiobook for GET endpoint test"
    audiobook_payload = {
        "description": audiobook_description,
        "default_speaker_id": speaker_id
    }
    create_audiobook_response = client.post(
        f"/api/works/{work_id}/audiobooks",
        json=audiobook_payload
    )
    assert create_audiobook_response.status_code == 200
    created_audiobook_data = create_audiobook_response.json()
    audiobook_id = created_audiobook_data["id"]
    assert created_audiobook_data["description"] == audiobook_description
    assert created_audiobook_data["original_work_id"] == work_id
    assert created_audiobook_data["default_speaker_id"] == speaker_id

    # 4. Call GET /api/audiobooks/{audiobook_id}
    get_audiobook_response = client.get(f"/api/audiobooks/{audiobook_id}")

    # 5. Assert that the response status code is 200
    assert get_audiobook_response.status_code == 200

    # 6. Assert that the response JSON contains the correct fields
    retrieved_audiobook_data = get_audiobook_response.json()
    assert retrieved_audiobook_data["id"] == audiobook_id
    assert retrieved_audiobook_data["original_work_id"] == work_id
    assert retrieved_audiobook_data["description"] == audiobook_description
    assert retrieved_audiobook_data["default_speaker_id"] == speaker_id
    assert "is_complete" in retrieved_audiobook_data  # Should exist
    assert retrieved_audiobook_data["is_complete"] == False # Initially false
    assert "generation_progress" in retrieved_audiobook_data # Should exist
    assert retrieved_audiobook_data["generation_progress"] == 0.0 # Initially 0.0
    assert "created_at" in retrieved_audiobook_data
    assert "updated_at" in retrieved_audiobook_data
    assert "default_speaker" not in retrieved_audiobook_data # This field is in the /details endpoint
    assert "characters" not in retrieved_audiobook_data # This field is in the /details endpoint

    # Test with a non-existent audiobook_id
    non_existent_audiobook_id = 99999
    get_non_existent_response = client.get(f"/api/audiobooks/{non_existent_audiobook_id}")
    assert get_non_existent_response.status_code == 404


def test_worker_fails_work_item(client, db_session, mock_glowfic_scraper, mock_speaker_model):
    # Setup: Create speaker, work, audiobook, and generate items
    speaker_name = "test_speaker_for_fail"
    speaker_response = client.post(
        "/api/speakers",
        data={"name": speaker_name, "model": "XTTS_v2"},
        files={"reference_audio": (f"{speaker_name}.wav", b"test audio data")}
    )
    assert speaker_response.status_code == 200
    speaker_id = speaker_response.json()["id"]

    work_response = client.post("/api/works/scrape_glowfic", json={"post_id": 9001}) # mock_glowfic_scraper
    assert work_response.status_code == 200
    work_id = work_response.json()["id"]

    audiobook_response = client.post(
        f"/api/works/{work_id}/audiobooks",
        json={"description": "Audiobook for fail test", "default_speaker_id": speaker_id}
    )
    assert audiobook_response.status_code == 200
    audiobook_id = audiobook_response.json()["id"]

    # Assign character voices to ensure items are generated for known characters
    # Mock work has "Alice" and "Bob"
    client.post(f"/api/audiobooks/{audiobook_id}/character-voices", json={"character_name": "Alice", "voice_name": speaker_name, "model": "XTTS_v2"})
    client.post(f"/api/audiobooks/{audiobook_id}/character-voices", json={"character_name": "Bob", "voice_name": speaker_name, "model": "XTTS_v2"})


    generate_response = client.post(f"/api/audiobooks/{audiobook_id}/generate")
    assert generate_response.status_code == 200
    assert generate_response.json()["queued_items"] > 0 # Should have items

    initial_status = client.get("/api/queue/status").json()
    assert initial_status["pending"] > 0

    # Take an item from the queue
    worker_id = "test_worker_fail"
    take_response = client.post("/api/queue/take", json={"worker_id": worker_id, "version": models.WORKER_VERSION})
    assert take_response.status_code == 200
    item_to_fail = take_response.json()
    assert item_to_fail is not None
    item_id = item_to_fail["id"]

    status_after_take = client.get("/api/queue/status").json()
    assert status_after_take["pending"] == initial_status["pending"] - 1
    assert status_after_take["in_progress"] == initial_status["in_progress"] + 1

    # Report the item as failed
    error_message = "Simulated worker error: Could not process audio."
    fail_response = client.post(
        f"/api/queue/{item_id}/fail/{worker_id}",
        json={"error_message": error_message}
    )
    assert fail_response.status_code == 200
    assert fail_response.json()["message"] == "Work item marked as failed."

    # Verify queue status shows the item as failed
    final_status = client.get("/api/queue/status").json()
    assert final_status["pending"] == status_after_take["pending"]
    assert final_status["in_progress"] == status_after_take["in_progress"] - 1
    assert final_status["failed"] == initial_status["failed"] + 1
    assert final_status["completed"] == initial_status["completed"]

    # Verify the database state for the WorkQueue item
    db_item = db_session.query(models.WorkQueue).filter(models.WorkQueue.id == item_id).first()
    assert db_item is not None
    assert db_item.status == models.WorkQueueStatus.failed
    assert db_item.error_message == error_message
    assert db_item.worker_id == worker_id


def test_api_error_handling_invalid_ids(client, db_session, mock_glowfic_scraper):
    non_existent_work_id = 99901
    non_existent_audiobook_id = 99902
    non_existent_speaker_name = "speaker_does_not_exist_xyz"

    # Attempt to create an audiobook for a non-existent work ID
    response = client.post(
        f"/api/works/{non_existent_work_id}/audiobooks",
        json={"description": "test", "default_speaker_id": 1} # dummy speaker id, work check is first
    )
    assert response.status_code == 404 # Expect Work not found

    # Attempt to assign a character voice to a non-existent audiobook ID
    response = client.post(
        f"/api/audiobooks/{non_existent_audiobook_id}/character-voices",
        json={"character_name": "SomeCharacter", "voice_name": "any_voice"}
    )
    assert response.status_code == 404 # Expect Audiobook not found

    # Setup for testing non-existent speaker assignment:
    # Create a real speaker
    real_speaker_name = "real_speaker_for_error_test"
    speaker_response = client.post(
        "/api/speakers",
        data={"name": real_speaker_name, "model": "XTTS_v2"},
        files={"reference_audio": (f"{real_speaker_name}.wav", b"test audio")}
    )
    assert speaker_response.status_code == 200
    real_speaker_id = speaker_response.json()["id"]

    # Create a real work
    work_response = client.post("/api/works/scrape_glowfic", json={"post_id": 9002}) # mock_glowfic_scraper
    assert work_response.status_code == 200
    real_work_id = work_response.json()["id"]

    # Create a real audiobook
    audiobook_response = client.post(
        f"/api/works/{real_work_id}/audiobooks",
        json={"description": "Audiobook for error test", "default_speaker_id": real_speaker_id}
    )
    assert audiobook_response.status_code == 200
    real_audiobook_id = audiobook_response.json()["id"]

    # Attempt to assign a non-existent speaker to a character
    response = client.post(
        f"/api/audiobooks/{real_audiobook_id}/character-voices",
        json={"character_name": "Alice", "voice_name": non_existent_speaker_name} # Alice from mock work
    )
    assert response.status_code == 404 # Expect Speaker (voice_name) not found

    # Attempt to generate an audiobook for a non-existent audiobook ID
    response = client.post(f"/api/audiobooks/{non_existent_audiobook_id}/generate")
    assert response.status_code == 404

    # Attempt to get WAV files for a non-existent audiobook ID
    response = client.get(f"/api/audiobooks/{non_existent_audiobook_id}/wav_files")
    assert response.status_code == 404

    # Attempt to get MP3 for a non-existent audiobook ID
    response = client.get(f"/api/audiobooks/{non_existent_audiobook_id}/mp3")
    assert response.status_code == 404


def test_api_404_catch_all_post(client):
    # Make a POST request to a clearly non-existent API endpoint
    response = client.post(
        "/api/this/route/does/absolutely/not/exist",
        json={"some_data": "does_not_matter"}
    )
    # Verify the response status code is 404
    assert response.status_code == 404
    # Verify the response body indicates a "Not found" or similar error
    # FastAPI's default 404 response for undefined routes is {"detail":"Not Found"}
    assert response.json() == {"detail": "Not Found"}

    # Also test with GET to a non-existent route
    response_get = client.get("/api/this/route/is/also/missing")
    assert response_get.status_code == 404
    assert response_get.json() == {"detail": "Not Found"}


# All parts of the original test_full_workflow have been moved to specific test functions.
# The test_full_workflow function has been removed.
