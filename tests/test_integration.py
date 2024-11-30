import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import os
from pathlib import Path
import json

from glowtalk import models, worker
from glowtalk.worker import Worker
from glowtalk.api import app, get_db
from glowtalk.models import Base, Speaker, SpeakerModel, WorkQueue, VoicePerformance
from conftest import mock_glowfic_scraper, mock_speaker_model, test_cwd, db_session, client, mock_combine_wav_to_mp3


def test_full_workflow(client, db_session, mock_glowfic_scraper, mock_speaker_model,
                      mock_combine_wav_to_mp3, test_cwd):
    # Test getting recent works (should be empty initially)
    response = client.get("/api/works/recent")
    assert response.status_code == 200
    assert response.json() == []

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

    # Test getting recent works (should now have our work)
    response = client.get("/api/works/recent")
    assert response.status_code == 200
    recent_works = response.json()
    assert len(recent_works) == 1
    assert recent_works[0]["id"] == work_id

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

    # Test getting audiobook details before setting character voices
    response = client.get(f"/api/audiobooks/{audiobook_id}/details")
    assert response.status_code == 200
    details = response.json()
    assert details["id"] == audiobook_id
    assert details["default_speaker"] == {
        "character_name": "Default speaker",
        "reference_voice": "alice",
        "model": "tts_models/multilingual/multi-dataset/xtts_v2"
    }
    # Characters should exist but have no voices assigned yet
    assert len(details["characters"]) == 2
    assert details["characters"] == [
        {
            "character_name": "Alice",
            "reference_voice": None,
            "model": None
        },
        {
            "character_name": "Bob",
            "reference_voice": None,
            "model": None
        }
    ]

    # 4. Assign Bob's voice to Bob's character and Alice's to Alice's
    response = client.post(
        f"/api/audiobooks/{audiobook_id}/character-voices",
        json={
            "character_name": "Alice",
            "voice_name": "alice",
            "model": None
        }
    )
    assert response.status_code == 200

    response = client.post(
        f"/api/audiobooks/{audiobook_id}/character-voices",
        json={
            "character_name": "Bob",
            "voice_name": "bob",
            "model": None
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


    response = client.get(f"/api/audiobooks/{audiobook_id}/details")
    assert response.status_code == 200
    audiobook_details = response.json()
    assert audiobook_details["id"] == audiobook_id
    assert audiobook_details["default_speaker"]['reference_voice'] == "alice"
    assert audiobook_details["characters"] == [
        {
            'character_name': 'Alice',
            'reference_voice': 'alice',
            'model': 'tts_models/multilingual/multi-dataset/xtts_v2'
        },
        {
            'character_name': 'Bob',
            'reference_voice': 'bob',
            'model': 'tts_models/multilingual/multi-dataset/xtts_v2'
        }
    ]

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

    # Test streaming content endpoint
    response = client.get(f"/api/audiobooks/{audiobook_id}/content")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/x-ndjson"

    # Split the response into lines and parse each as JSON
    parts = [json.loads(line) for line in response.text.strip().split('\n')]
    assert len(parts) == 2  # Two parts: Alice's and Bob's

    # Verify Alice's part
    alice_part = parts[0]
    assert alice_part["character_name"] == "Alice"
    assert alice_part["screenname"] == "AliceScreen"
    assert alice_part["author_name"] == "AuthorOne"

    # Verify Alice's content pieces
    alice_pieces = alice_part["content_pieces"]
    assert [piece["text"] for piece in alice_pieces] == [
        "Alice (AliceScreen) (by AuthorOne):",
        "\n\n",
        "Hello there!",
        "This is Alice speaking.",
        "\n"
    ]
    voiced_alice_pieces = [piece for piece in alice_pieces if piece["voiced"]]
    assert [piece["text"] for piece in voiced_alice_pieces] == [
        "Alice (AliceScreen) (by AuthorOne):",
        "Hello there!",
        "This is Alice speaking.",
    ]
    # All voiced pieces should have audio file hashes
    assert all(piece["audio_file_hash"] for piece in voiced_alice_pieces)

    # Verify Bob's part
    bob_part = parts[1]
    assert bob_part["character_name"] == "Bob"
    assert bob_part["screenname"] == "BobScreen"
    assert bob_part["author_name"] == "AuthorTwo"

    # Verify Bob's content pieces
    bob_pieces = bob_part["content_pieces"]
    assert [piece["text"] for piece in bob_pieces] == [
        "Bob (BobScreen) (by AuthorTwo):",
        "\n\n",
        "Hi Alice!",
        "This is Bob.",
        "\n"
    ]
    voiced_bob_pieces = [piece for piece in bob_pieces if piece["voiced"]]
    assert [piece["text"] for piece in voiced_bob_pieces] == [
        "Bob (BobScreen) (by AuthorTwo):",
        "Hi Alice!",
        "This is Bob.",
    ]
    # All voiced pieces should have audio file hashes
    assert all(piece["audio_file_hash"] for piece in voiced_bob_pieces)
