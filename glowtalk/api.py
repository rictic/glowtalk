from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, File, Form, UploadFile
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, HttpUrl, ConfigDict
from datetime import datetime
from . import models
from .database import init_db
import os
import json
import re
from pathlib import Path
from glowtalk import glowfic_scraper

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
            priority=0
        )
        db.add(queue_item)
        i += 1

    db.commit()
    return {"message": "Generation started", "queued_items": i}

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
