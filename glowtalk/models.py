from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.ext.orderinglist import ordering_list
from datetime import datetime

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
    should_voice = Column(Boolean, default=True)
    position = Column(Integer)

    # Relationships
    part = relationship("Part", back_populates="content_pieces")
    performances = relationship("VoicePerformance", back_populates="content_piece")

class Audiobook(Base):
    __tablename__ = 'audiobooks'

    id = Column(Integer, primary_key=True)
    original_work_id = Column(Integer, ForeignKey('original_works.id'), nullable=False)

    # Relationships
    original_work = relationship("OriginalWork", back_populates="audiobooks")
    performances = relationship(
        "VoicePerformance",
        back_populates="audiobook",
        order_by="VoicePerformance.position",
        collection_class=ordering_list('position')
    )

class VoicePerformance(Base):
    __tablename__ = 'voice_performances'

    id = Column(Integer, primary_key=True)
    audiobook_id = Column(Integer, ForeignKey('audiobooks.id'), nullable=False)
    content_piece_id = Column(Integer, ForeignKey('content_pieces.id'), nullable=False)
    speaker_id = Column(Integer, ForeignKey('speakers.id'), nullable=False)
    audio_file_path = Column(String, nullable=False)
    audio_file_hash = Column(String, nullable=False)
    is_preferred = Column(Boolean, default=False)
    position = Column(Integer)

    # Relationships
    audiobook = relationship("Audiobook", back_populates="performances")
    content_piece = relationship("ContentPiece", back_populates="performances")
    speaker = relationship("Speaker")

class Speaker(Base):
    __tablename__ = 'speakers'

    id = Column(Integer, primary_key=True)
    model_id = Column(String, nullable=False)
    reference_audio_path = Column(String, nullable=False)
    reference_audio_hash = Column(String, nullable=False)
