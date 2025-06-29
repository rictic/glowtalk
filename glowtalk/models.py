from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, UniqueConstraint, Enum, Table
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.ext.orderinglist import ordering_list
from sqlalchemy.orm import Session

from datetime import datetime, timedelta
import enum
import hashlib
import os
from pathlib import Path
from typing import Optional, Iterator
from glowtalk import convert
import time
import uuid

Base = declarative_base()

class OriginalWork(Base):
    __tablename__ = 'original_works'

    id = Column(Integer, primary_key=True)
    url = Column(String, nullable=False)
    title = Column(String, nullable=True)
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

    def get_num_content_pieces(self, session: Session):
        """Get the number of content pieces for this work"""
        return session.query(ContentPiece)\
            .join(Part)\
            .filter(Part.original_work_id == self.id)\
            .count()

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

    def perform_for_audiobook(self, session: Session, audiobook: 'Audiobook') -> 'VoicePerformance':
        speaker = self.get_speaker_for_audiobook(session, audiobook)
        if not speaker:
            raise ValueError(f"No speaker configured for content piece {self.text} or for character {self.character or self.part.character} and no default speaker in this audiobook.")
        return speaker.generate_voice_performance(session, self, audiobook)

    def get_performance_for_audiobook(self, session: Session, audiobook: 'Audiobook') -> Optional['VoicePerformance']:
        if not self.should_voice:
            return None
        speaker = self.get_speaker_for_audiobook(session, audiobook)
        if not speaker:
            return None
        # now get the performance for this speaker and content piece
        # TODO: need to account for an audiobook's preferred performance
        performance = session.query(VoicePerformance)\
            .filter(VoicePerformance.speaker_id == speaker.id, VoicePerformance.content_piece_id == self.id)\
            .order_by(VoicePerformance.generation_date.desc())\
            .first()
        return performance


class Audiobook(Base):
    __tablename__ = 'audiobooks'

    id = Column(Integer, primary_key=True)
    original_work_id = Column(Integer, ForeignKey('original_works.id'), nullable=False)
    default_speaker_id = Column(Integer, ForeignKey('speakers.id'), nullable=True)
    description = Column(String, nullable=True)
    forked_from_id = Column(Integer, ForeignKey('audiobooks.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    mp3_path = Column(String, nullable=True)

    # Relationships
    original_work = relationship("OriginalWork", back_populates="audiobooks")
    default_speaker = relationship("Speaker", foreign_keys=[default_speaker_id])
    character_voices = relationship("CharacterVoice", back_populates="audiobook")
    forked_from = relationship("Audiobook", remote_side=[id])
    queue_items = relationship("WorkQueue", back_populates="audiobook")

    def ready_to_generate(self, session: Session):
        """Check if this audiobook is ready to generate"""
        # if we have a default speaker, we're ready
        if self.default_speaker:
            return True
        # if we don't have a default speaker, query looking for any part
        # that doesn't have a character voice for this audiobook
        # hm, but that's not possible in our current schema. need to change that
        raise NotImplementedError("Not implemented")

    def get_wav_files(self, session: Session) -> Iterator[Path]:
        """Get all the wav files for this audiobook"""
        return (Path(performance.audio_file_path) for performance in self.get_performances(session))

    def get_performances(self, session: Session) -> Iterator['VoicePerformance']:
        # Inefficient, but it's a start. Go through each content piece in each
        # part, determine our preferred speaker, and get the audio file path
        # for it
        original_work = self.original_work
        for part in original_work.parts:
            for content_piece in part.content_pieces:
                if not content_piece.should_voice:
                    continue
                performance = content_piece.get_performance_for_audiobook(session, self)
                if not performance:
                    raise ValueError(f"No performance found for content piece {content_piece.text} (id {content_piece.id})")
                yield performance

    def add_work_queue_items(self, session: Session):
        # Get all content pieces that need voicing.
        # We want to search for content pieces that are part of the original
        # work for this audiobook, and that should be voiced.
        should_voice = session.query(ContentPiece)\
            .join(Part)\
            .join(OriginalWork)\
            .filter(
                ContentPiece.should_voice == True,
                ContentPiece.part_id == Part.id,
                OriginalWork.id == self.original_work_id,
            )\
            .all()

        # Add them to the work queue
        added_count = 0
        for piece in should_voice:
            speaker = piece.get_speaker_for_audiobook(session, self)
            # Does this speaker already have a performance for this content piece?
            existing_performance = session.query(VoicePerformance)\
                .filter(VoicePerformance.speaker_id == speaker.id, VoicePerformance.content_piece_id == piece.id)\
                .first()
            if existing_performance:
                continue
            # Do we already have a work queue item for this content piece and speaker?
            existing_queue_item = session.query(WorkQueue)\
                .filter(WorkQueue.content_piece_id == piece.id, WorkQueue.speaker_id == speaker.id)\
                .first()
            if existing_queue_item:
                continue
            # Add the work queue item
            queue_item = WorkQueue(
                content_piece_id=piece.id,
                audiobook_id=self.id,
                speaker_id=speaker.id,
                priority=10
            )
            session.add(queue_item)
            added_count += 1
        session.commit()
        return added_count

    def generate_mp3(self, session: Session):
        """Generate an MP3 file for this audiobook"""
        filename = str(uuid.uuid4()) + ".mp3"
        output_path = Path(os.getcwd()) / "outputs" / filename
        output_path = output_path.resolve()
        wav_files = self.get_wav_files(session)
        convert.combine_wav_to_mp3(wav_files, output_path)
        self.mp3_path = str(output_path)
        session.add(self)
        session.commit()
        return output_path

    def get_or_generate_mp3(self, session: Session):
        if self.mp3_path:
            return Path(self.mp3_path)
        return self.generate_mp3(session)

class VoicePerformance(Base):
    __tablename__ = 'voice_performances'

    id = Column(Integer, primary_key=True)
    audiobook_id = Column(Integer, ForeignKey('audiobooks.id'), nullable=False)
    content_piece_id = Column(Integer, ForeignKey('content_pieces.id'), nullable=False)
    speaker_id = Column(Integer, ForeignKey('speakers.id'), nullable=False)
    audio_file_path = Column(String, nullable=False)
    audio_file_hash = Column(String, nullable=False)
    generation_date = Column(DateTime, default=datetime.utcnow)
    worker_id = Column(String, nullable=True)

    # Relationships
    audiobook = relationship("Audiobook")
    content_piece = relationship("ContentPiece", back_populates="performances")
    speaker = relationship("Speaker")


class SpeakerModel(enum.Enum):
    XTTS_v2 = "tts_models/multilingual/multi-dataset/xtts_v2"

    @classmethod
    def default(cls):
        return cls.XTTS_v2

_speaker_model = None

class ReferenceVoice(Base):
    __tablename__ = 'reference_voices'

    id = Column(Integer, primary_key=True)
    audio_path = Column(String, nullable=False)
    audio_hash = Column(String, nullable=False)
    description = Column(String, nullable=True)
    transcript = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    name = Column(String, nullable=False)

    # Relationships
    speakers = relationship("Speaker", back_populates="reference_voice")

    # We want to enforce that the name is unique
    __table_args__ = (
        UniqueConstraint('name', name='unique_name'),
    )

    @classmethod
    def get_by_name(cls, session: Session, name: str):
        return session.query(cls).filter_by(name=name).first()

    # This should probably be deleted, since we're moving to
    # paths built on hashes.
    @classmethod
    def get_or_create(cls, session: Session, audio_path: Path, name: str, description=None, transcript=None):
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
                name=name,
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
    def get_or_create_with_reference_voice(cls, session: Session, reference_voice: ReferenceVoice, name: str, model: SpeakerModel):
        speaker = session.query(cls).filter_by(reference_voice=reference_voice, model=model).first()
        if not speaker:
            speaker = cls(reference_voice=reference_voice, model=model)
            session.add(speaker)
        return speaker

    @classmethod
    def get_or_create(cls, session: Session, name: str, model: SpeakerModel, description=None, transcript=None):
        reference_audio_path = Path(os.getcwd()) / "references" / f"{name}.wav"
        reference_voice = ReferenceVoice.get_or_create(
            session,
            reference_audio_path,
            name=name,
            description=description,
            transcript=transcript
        )

        speaker = session.query(cls).filter_by(reference_voice=reference_voice).first()
        if not speaker:
            speaker = cls(model=model, reference_voice=reference_voice)
            session.add(speaker)
        return speaker

    def generate_voice_performance(self, session: Session, content_piece: ContentPiece, audiobook: Audiobook) -> VoicePerformance:
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

    @classmethod
    def get_or_update(cls, session, audiobook, character_name, speaker):
        existing = session.query(cls).filter_by(audiobook=audiobook, character_name=character_name).first()
        if not existing:
            existing = cls(audiobook=audiobook, character_name=character_name, speaker=speaker)
            session.add(existing)
        else:
            existing.speaker = speaker
        return existing

class WorkQueue(Base):
    __tablename__ = 'work_queue'

    id = Column(Integer, primary_key=True)
    content_piece_id = Column(Integer, ForeignKey('content_pieces.id'), nullable=False)
    audiobook_id = Column(Integer, ForeignKey('audiobooks.id'), nullable=False)
    speaker_id = Column(Integer, ForeignKey('speakers.id'), nullable=False)
    created_voice_performance_id = Column(Integer, ForeignKey('voice_performances.id'), nullable=True)
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
    speaker = relationship("Speaker")
    created_voice_performance = relationship("VoicePerformance", foreign_keys=[created_voice_performance_id])

    @classmethod
    def assign_work_item(cls, session: Session, worker_id: str) -> Optional['WorkQueue']:
        # Find the highest priority work item that is either:
        # 1. pending, or
        # 2. in progress but stale (started more than 2 minutes ago)
        work_item = session.query(cls)\
            .filter(
                (cls.status == 'pending') |
                (
                    (cls.status == 'in_progress') &
                    (cls.started_at < datetime.utcnow() - timedelta(minutes=2))
                )
            )\
            .order_by(cls.priority.desc(), cls.created_at.asc()).first()
        if work_item is None:
            # Try to take the highest priority in progress item then
            work_item = session.query(cls)\
                .filter(cls.status == 'in_progress')\
                .order_by(cls.priority.desc(), cls.created_at.asc()).first()
        if work_item is None:
            return None
        work_item.worker_id = worker_id
        work_item.status = 'in_progress'
        work_item.started_at = datetime.utcnow()
        session.add(work_item)
        session.commit()
        return work_item

    def complete_work_item(self, session: Session, worker_id: str, created_voice_performance: VoicePerformance):
        if self.status == 'completed':
            return
        if self.status == 'failed':
            self.error_message = None
        self.worker_id = worker_id
        self.status = 'completed'
        self.completed_at = datetime.utcnow()
        self.created_voice_performance = created_voice_performance
        session.add(self)
        session.add(created_voice_performance)
        session.add(self.audiobook)
        session.commit()

    def fail_work_item(self, session: Session, worker_id: str, error_message: str):
        if self.status == 'failed':
            return
        if self.status == 'completed':
            self.error_message = None
            return
        self.worker_id = worker_id
        self.status = 'failed'
        self.error_message = error_message
        session.add(self)
        session.commit()
