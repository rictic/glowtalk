from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, File, Form, UploadFile
from sqlalchemy.orm import Session
from typing import List, Optional, Union
from pydantic import BaseModel, HttpUrl, ConfigDict, Field
from datetime import datetime
from . import models
from .database import init_db
import os
import json
import re
from pathlib import Path
from glowtalk import glowfic_scraper
from fastapi.responses import FileResponse
import hashlib

app = FastAPI()

# --- Dependency ---
def get_db():
    db = init_db()
    try:
        yield db
    finally:
        db.close()

# --- Pydantic Models ---
# Request Models
class ScrapeGlowficRequest(BaseModel):
    post_id: int

# Response Models
class WorkResponse(BaseModel):
    id: int
    url: str
    scrape_date: datetime

    model_config = ConfigDict(from_attributes=True)

class AudiobookResponse(BaseModel):
    id: int
    original_work_id: int
    description: Optional[str] = None
    default_speaker_id: Optional[int] = None
    forked_from_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class CharacterVoiceResponse(BaseModel):
    id: int
    character_name: str
    speaker_id: int
    audiobook_id: int

    model_config = ConfigDict(from_attributes=True)

class SpeakerResponse(BaseModel):
    id: int
    model: str

    model_config = ConfigDict(from_attributes=True)

class SpeakerCreate(BaseModel):
    name: str
    model: models.SpeakerModel

class CharacterVoiceCreate(BaseModel):
    character_name: str
    speaker_id: int

class AudiobookCreate(BaseModel):
    description: Optional[str] = None
    default_speaker_id: Optional[int] = None
    forked_from_id: Optional[int] = None

class TakeWorkRequest(BaseModel):
    worker_id: str
    version: int

class WorkQueueItemResponse(BaseModel):
    id: int
    text: str
    speaker_model: str
    reference_audio_hash: str

    model_config = ConfigDict(from_attributes=True)

class WorkItemCompletionRequest(BaseModel):
    worker_id: str
    performance_path: str


# --- API Routes ---

@app.get("/api/works/{work_id}", response_model=WorkResponse)
def get_work(work_id: int, db: Session = Depends(get_db)):
    """Get details about a specific work including its parts and audiobooks"""
    work = db.get(models.OriginalWork, work_id)
    if not work:
        raise HTTPException(status_code=404, detail="Work not found")
    return work

@app.post("/api/works/scrape_glowfic", response_model=WorkResponse)
def create_work(request: ScrapeGlowficRequest, db: Session = Depends(get_db)):
    """Create a new work by URL, triggering scraping in the background"""
    new_work = glowfic_scraper.scrape_post(request.post_id, db)
    db.add(new_work)
    db.commit()
    db.refresh(new_work)  # Refresh to ensure we have the latest data
    return new_work

@app.get("/api/audiobooks/{audiobook_id}", response_model=AudiobookResponse)
def get_audiobook(audiobook_id: int, db: Session = Depends(get_db)):
    """Get details about a specific audiobook including its character voices"""
    audiobook = db.get(models.Audiobook, audiobook_id)
    if not audiobook:
        raise HTTPException(status_code=404, detail="Audiobook not found")
    return audiobook

@app.post("/api/works/{work_id}/audiobooks", response_model=AudiobookResponse)
def create_audiobook(
    work_id: int,
    audiobook: AudiobookCreate,
    db: Session = Depends(get_db)
):
    """Create a new audiobook for a work"""
    work = db.get(models.OriginalWork, work_id)
    if not work:
        raise HTTPException(status_code=404, detail="Work not found")

    # Verify speaker exists if specified
    if audiobook.default_speaker_id:
        speaker = db.get(models.Speaker, audiobook.default_speaker_id)
        if not speaker:
            raise HTTPException(status_code=404, detail="Speaker not found")

    new_audiobook = models.Audiobook(
        original_work_id=work_id,
        description=audiobook.description,
        default_speaker_id=audiobook.default_speaker_id,
        forked_from_id=audiobook.forked_from_id
    )
    db.add(new_audiobook)
    db.commit()
    db.refresh(new_audiobook)
    return new_audiobook

@app.post("/api/audiobooks/{audiobook_id}/character-voices", response_model=CharacterVoiceResponse)
def set_character_voice(
    audiobook_id: int,
    voice: CharacterVoiceCreate,
    db: Session = Depends(get_db)
):
    """Set or update a character's voice in an audiobook"""
    speaker = db.get(models.Speaker, voice.speaker_id)
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")

    audiobook = db.get(models.Audiobook, audiobook_id)
    if not audiobook:
        raise HTTPException(status_code=404, detail="Audiobook not found")

    char_voice = models.CharacterVoice.get_or_create(
        db, audiobook, voice.character_name, speaker
    )
    db.commit()
    db.refresh(char_voice)  # Ensure we have the latest data
    return char_voice

def save_reference_audio(file_content: bytes, name: str):
    # Ensure that name is purely alphanumeric plus spaces, underscores, and hyphens
    if not re.match(r'^[a-zA-Z0-9 _-]+$', name):
        raise ValueError(f"Reference audio name must be purely alphanumeric plus spaces, underscores, and hyphens, got {json.dumps(name)}")
    # We save to the references/ directory.
    # create a Path for cwd / 'references' / <name>.wav
    target_path = Path(os.getcwd()) / 'references' / f"{name}.wav"

    # Verify that it does not clash
    if target_path.exists():
        raise ValueError(f"A reference audio file with the name {name}.wav already exists")
    target_path.write_bytes(file_content)

@app.post("/api/speakers", response_model=SpeakerResponse)
async def create_speaker(
    name: str = Form(...),
    model: str = Form(...),
    reference_audio: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Create a new speaker with a reference audio file"""
    try:
        # Save the uploaded file and get its path
        file_content = await reference_audio.read()
        # Raise if file content is not bytes
        if not isinstance(file_content, bytes):
            raise ValueError("Reference audio must be a bytes object")
        save_reference_audio(file_content, name)
        # Try to convert the model string to a SpeakerModel enum
        model = models.SpeakerModel[model]

        new_speaker = models.Speaker.get_or_create(
            db,
            name=name,
            model=model,
        )
        db.commit()
        db.refresh(new_speaker)
        return new_speaker
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/reference_voices/{audio_hash}", response_class=FileResponse)
def get_reference_voice(audio_hash: str, db: Session = Depends(get_db)):
    """Get a specific reference voice"""
    reference_voice = db.query(models.ReferenceVoice).filter(models.ReferenceVoice.audio_hash == audio_hash).first()
    if not reference_voice:
        raise HTTPException(status_code=404, detail="Reference voice not found")
    return FileResponse(reference_voice.audio_path)

@app.post("/api/audiobooks/{audiobook_id}/generate")
def generate_audiobook(
    audiobook_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Start generating an audiobook by adding all unvoiced content to the work queue"""
    audiobook = db.get(models.Audiobook, audiobook_id)
    if not audiobook:
        raise HTTPException(status_code=404, detail="Audiobook not found")

    # Get all content pieces that need voicing
    unvoiced = models.ContentPiece.get_unvoiced(db)

    # Add them to the work queue
    i = 0
    for piece in unvoiced:
        queue_item = models.WorkQueue(
            content_piece_id=piece.id,
            audiobook_id=audiobook_id,
            speaker_id=piece.get_speaker_for_audiobook(db, audiobook).id,
            priority=0
        )
        db.add(queue_item)
        i += 1

    db.commit()
    return {"message": "Generation started", "queued_items": i}

@app.post("/api/queue/take", response_model=Optional[WorkQueueItemResponse])
def assign_work_item(request: TakeWorkRequest, db: Session = Depends(get_db)):
    """Assign a pending work item to a worker"""
    if request.version != 1:
        # Servers should be backwards compatible, but not ready to commit
        # to being forward compatible yet.
        return None

    item = models.WorkQueue.assign_work_item(db, request.worker_id)
    if item is None:
        return None
    speaker = item.content_piece.get_speaker_for_audiobook(db, item.audiobook)

    return WorkQueueItemResponse(
        id = item.id,
        text = item.content_piece.text,
        speaker_model = speaker.model,
        reference_audio_hash = speaker.reference_voice.audio_hash
    )


@app.post("/api/queue/{item_id}/complete/{worker_id}", response_model=None)
async def complete_work_item(
    item_id: int,
    worker_id: str,
    generated_audio: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Create a voice performance and use it to complete a work item."""
    item = db.get(models.WorkQueue, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Work item not found")

    # Save the uploaded file to the outputs directory using the item's hash as the filename
    file_content = await generated_audio.read()
    file_hash = hashlib.sha256(file_content).hexdigest()
    output_dir = Path(os.getcwd()) / 'outputs'
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"{file_hash}.wav"
    # Normalize the path
    output_path = output_path.resolve()
    if not output_path.exists():
        output_path.write_bytes(file_content)

    # Create the performance record and complete the work item
    performance = models.VoicePerformance(
        content_piece_id=item.content_piece_id,
        audiobook_id=item.audiobook_id,
        speaker_id=item.speaker_id,
        audio_file_path=str(output_path),
        audio_file_hash=file_hash,
        worker_id=worker_id
    )
    db.add(performance)
    item.complete_work_item(db, worker_id, performance)

    db.commit()
    db.refresh(item)

@app.get("/api/queue/status")
def get_queue_status(db: Session = Depends(get_db)):
    """Get the current status of the work queue"""
    pending = db.query(models.WorkQueue)\
        .filter(models.WorkQueue.status == 'pending').count()
    in_progress = db.query(models.WorkQueue)\
        .filter(models.WorkQueue.status == 'in_progress').count()
    completed = db.query(models.WorkQueue)\
        .filter(models.WorkQueue.status == 'completed').count()
    failed = db.query(models.WorkQueue)\
        .filter(models.WorkQueue.status == 'failed').count()

    return {
        "pending": pending,
        "in_progress": in_progress,
        "completed": completed,
        "failed": failed
    }
