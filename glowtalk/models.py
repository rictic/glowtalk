from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, UniqueConstraint, Enum
import enum
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.ext.orderinglist import ordering_list
from datetime import datetime
import hashlib
import os
from sqlalchemy.orm import Session

Base = declarative_base()

class OriginalWork(Base):
    __tablename__ = 'original_works'

    id = Column(Integer, primary_key=True)
    url = Column(String, nullable=False)
    scrape_date = Column(DateTime, default=datetime.utcnow)

    # Relationships
    audiobooks = relationship("Audiobook", back_populates="original_work")
    parts = relationship(
        "Part",
        back_populates="original_work",
        order_by="Part.position",
        collection_class=ordering_list('position')
    )

    @classmethod
    def get_by_url_latest(cls, session, url):
        """Get the most recently scraped version of a work with the given URL."""
        return session.query(cls)\
            .filter(cls.url == url)\
            .order_by(cls.scrape_date.desc())\
            .first()

class Part(Base):
    __tablename__ = 'parts'

    id = Column(Integer, primary_key=True)
    original_work_id = Column(Integer, ForeignKey('original_works.id'), nullable=False)
    position = Column(Integer)

    # Metadata
    title = Column(String, nullable=True)
    author = Column(String, nullable=True)
    icon_url = Column(String, nullable=True)
    icon_title = Column(String, nullable=True)
    character = Column(String, nullable=True)
    screenname = Column(String, nullable=True)

    # Relationships
    original_work = relationship("OriginalWork", back_populates="parts")
    content_pieces = relationship(
        "ContentPiece",
        back_populates="part",
        order_by="ContentPiece.position",
        collection_class=ordering_list('position')
    )

class ContentPiece(Base):
    __tablename__ = 'content_pieces'

    id = Column(Integer, primary_key=True)
    part_id = Column(Integer, ForeignKey('parts.id'), nullable=False)
    text = Column(String, nullable=False)
    character = Column(String, nullable=True)
    should_voice = Column(Boolean, default=True)
    position = Column(Integer)

    # Relationships
    part = relationship("Part", back_populates="content_pieces")
    performances = relationship("VoicePerformance", back_populates="content_piece")

    @classmethod
    def get_unvoiced(cls, session):
        """Get all content pieces that should be voiced but don't have a performance yet"""
        return session.query(cls)\
            .outerjoin(VoicePerformance)\
            .filter(
                cls.should_voice == True,
                VoicePerformance.id == None
            )

    def get_speaker_for_audiobook(self, session: Session, audiobook: 'Audiobook') -> Optional['Speaker']:
        """Get the speaker for this content piece for a given audiobook"""
        # if we have a character, try to find their voice in the audiobook
        if self.character:
            specific_speaker = session.query(Speaker)\
                .join(CharacterVoice)\
                .filter(CharacterVoice.audiobook_id == audiobook.id, CharacterVoice.character_name == self.character)\
                .first()
            if specific_speaker:
                return specific_speaker
        # if our part has a character, try to find their voice in the audiobook
        if self.part.character:
            specific_speaker = session.query(Speaker)\
                .join(CharacterVoice)\
                .filter(CharacterVoice.audiobook_id == audiobook.id, CharacterVoice.character_name == self.part.character)\
                .first()
            if specific_speaker:
                return specific_speaker
        # otherwise, use the default speaker for the audiobook
        return audiobook.default_speaker

    def perform_for_audiobook(self, session: Session, audiobook: 'Audiobook'):
        speaker = self.get_speaker_for_audiobook(session, audiobook)
        if not speaker:
            raise ValueError(f"No speaker configured for content piece {self.text} or for character {self.character or self.part.character} and no default speaker in this audiobook.")
        return speaker.generate_voice_performance(session, self, audiobook)

class Audiobook(Base):
    __tablename__ = 'audiobooks'

    id = Column(Integer, primary_key=True)
    original_work_id = Column(Integer, ForeignKey('original_works.id'), nullable=False)
    default_speaker_id = Column(Integer, ForeignKey('speakers.id'), nullable=True)
    description = Column(String, nullable=True)
    forked_from_id = Column(Integer, ForeignKey('audiobooks.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    original_work = relationship("OriginalWork", back_populates="audiobooks")
    default_speaker = relationship("Speaker", foreign_keys=[default_speaker_id])
    character_voices = relationship("CharacterVoice", back_populates="audiobook")
    forked_from = relationship("Audiobook", remote_side=[id])
    queue_items = relationship("WorkQueue", back_populates="audiobook")

class VoicePerformance(Base):
    __tablename__ = 'voice_performances'

    id = Column(Integer, primary_key=True)
    audiobook_id = Column(Integer, ForeignKey('audiobooks.id'), nullable=False)
    content_piece_id = Column(Integer, ForeignKey('content_pieces.id'), nullable=False)
    speaker_id = Column(Integer, ForeignKey('speakers.id'), nullable=False)
    audio_file_path = Column(String, nullable=False)
    audio_file_hash = Column(String, nullable=False)
    is_preferred = Column(Boolean, default=False)
    generation_date = Column(DateTime, default=datetime.utcnow)
    worker_id = Column(String, nullable=True)

    # Relationships
    audiobook = relationship("Audiobook")
    content_piece = relationship("ContentPiece", back_populates="performances")
    speaker = relationship("Speaker")


class SpeakerModel(enum.Enum):
    XTTS_v2 = "tts_models/multilingual/multi-dataset/xtts_v2"

_speaker_model = None

class ReferenceVoice(Base):
    __tablename__ = 'reference_voices'

    id = Column(Integer, primary_key=True)
    audio_path = Column(String, nullable=False)
    audio_hash = Column(String, nullable=False)
    description = Column(String, nullable=True)
    transcript = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    speakers = relationship("Speaker", back_populates="reference_voice")

    @classmethod
    def get_or_create(cls, session: Session, audio_path: Path, description=None, transcript=None):
        """Get or create a reference voice from an audio file"""
        # Check that the path is a Path
        if not isinstance(audio_path, Path):
            raise ValueError(f"audio_path must be a Path, not {type(audio_path)}")
        if not audio_path.exists():
            raise ValueError(f"Reference audio file not found: {audio_path}")
        # normalize the path
        audio_path = audio_path.resolve()

        reference = session.query(cls).filter_by(audio_path=str(audio_path)).first()
        if not reference:
            audio_hash = hashlib.sha256(open(audio_path, "rb").read()).hexdigest()
            reference = cls(
                audio_path=str(audio_path),
                audio_hash=audio_hash,
                description=description,
                transcript=transcript
            )
            session.add(reference)
        return reference

class Speaker(Base):
    __tablename__ = 'speakers'

    id = Column(Integer, primary_key=True)
    model = Column(Enum(SpeakerModel), nullable=False)
    reference_voice_id = Column(Integer, ForeignKey('reference_voices.id'), nullable=False)

    # Relationships
    reference_voice = relationship("ReferenceVoice", back_populates="speakers")

    @classmethod
    def get_or_create(cls, session: Session, name: str, model: SpeakerModel, description=None, transcript=None):
        reference_audio_path = Path(os.getcwd()) / "references" / f"{name}.wav"
        reference_voice = ReferenceVoice.get_or_create(
            session,
            reference_audio_path,
            description=description,
            transcript=transcript
        )

        speaker = session.query(cls).filter_by(reference_voice=reference_voice).first()
        if not speaker:
            speaker = cls(model=model, reference_voice=reference_voice)
            session.add(speaker)
        return speaker

    def generate_voice_performance(self, session: Session, content_piece: ContentPiece, audiobook: Audiobook):
        global _speaker_model
        if not _speaker_model:
            import glowtalk.speak
            _speaker_model = glowtalk.speak.Speaker(model=self.model.value)
        audio_path = _speaker_model.speak(content_piece.text, self.reference_voice.audio_path)
        # normalize the path
        audio_path = audio_path.resolve()
        audio_hash = hashlib.sha256(open(audio_path, "rb").read()).hexdigest()
        performance = VoicePerformance(
            audiobook=audiobook,
            content_piece=content_piece,
            speaker=self,
            audio_file_path=str(audio_path),
            audio_file_hash=audio_hash,
        )
        session.add(performance)

        return performance


class CharacterVoice(Base):
    __tablename__ = 'character_voices'

    id = Column(Integer, primary_key=True)
    audiobook_id = Column(Integer, ForeignKey('audiobooks.id'), nullable=False)
    character_name = Column(String, nullable=False)
    speaker_id = Column(Integer, ForeignKey('speakers.id'), nullable=False)

    # Relationships
    audiobook = relationship("Audiobook", back_populates="character_voices")
    speaker = relationship("Speaker")

    # Ensure we don't have duplicate character names for the same audiobook
    __table_args__ = (
        UniqueConstraint('audiobook_id', 'character_name', name='unique_character_per_audiobook'),
    )

    @classmethod
    def get_or_create(cls, session, audiobook, character_name, speaker):
        existing = session.query(cls).filter_by(audiobook=audiobook, character_name=character_name).first()
        if not existing:
            existing = cls(audiobook=audiobook, character_name=character_name, speaker=speaker)
            session.add(existing)
        else:
            assert existing.speaker == speaker
        return existing

class WorkQueue(Base):
    __tablename__ = 'work_queue'

    id = Column(Integer, primary_key=True)
    content_piece_id = Column(Integer, ForeignKey('content_pieces.id'), nullable=False)
    audiobook_id = Column(Integer, ForeignKey('audiobooks.id'), nullable=False)
    priority = Column(Integer, default=0)  # Higher number = higher priority
    status = Column(Enum('pending', 'in_progress', 'completed', 'failed', name='queue_status'), default='pending')
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    worker_id = Column(String, nullable=True)  # ID of the worker processing this item
    error_message = Column(String, nullable=True)

    # Relationships
    content_piece = relationship("ContentPiece")
    audiobook = relationship("Audiobook")
