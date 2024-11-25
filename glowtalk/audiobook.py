from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional
import os

from .glowfic_scraper import Glowfic, Post

@dataclass
class Reader:
    """Represents a voice that can read parts of the audiobook"""
    name: str
    reference_path: Path

    def __post_init__(self):
        """Verify the reference audio file exists"""
        if not self.reference_path.exists():
            raise FileNotFoundError(f"Reference audio not found: {self.reference_path}")

    @classmethod
    def from_name(cls, name: str) -> 'Reader':
        """Create a Reader from just a name, using the default references directory"""
        reference_path = Path("references") / f"{name}.wav"
        return cls(name=name, reference_path=reference_path)

@dataclass
class Audiobook:
    """Represents a Glowfic story configured for audio generation"""
    glowfic: Glowfic
    default_reader: Reader
    character_readers: Dict[str, Reader]

    def get_reader_for_post(self, post: Post) -> Reader:
        """Get the configured reader for a given post"""
        if post.character is None:
            return self.default_reader
        return self.character_readers.get(post.character, self.default_reader)

