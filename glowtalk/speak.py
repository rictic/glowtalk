import re
import os
from pathlib import Path
import tempfile
import torch
from TTS.api import TTS
from .audiobook import Reader
import pysbd

def get_unique_filename() -> Path:
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(exist_ok=True)

    existing_files = list(outputs_dir.glob("output *.wav"))
    max_counter = -1
    pattern = re.compile(r"output (\d+)\.wav")
    for file in existing_files:
        match = pattern.match(file.name)
        if match:
            counter = int(match.group(1))
            max_counter = max(max_counter, counter)

    counter = max_counter + 1
    while True:
        # try to create our candidate filename in exclusive mode, to handle
        # race conditions
        filename = f"output {counter}.wav"
        file_path = outputs_dir / filename

        try:
            with file_path.open("x") as f:
                return file_path
        except FileExistsError:
            counter += 1

segmenter = pysbd.Segmenter(language="en", clean=True)

class Speaker:
  def __init__(self):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
      print("pytorch isn't happy with your cuda so this will be slower")

    self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)

  def speak(self, text: str, reader: Reader, language="en", **kwargs) -> list[Path]:
    segments = segmenter.segment(normalize_text(text))
    filenames = []
    for segment in segments:
      filename = get_unique_filename()
      self.tts.tts_to_file(
          text=normalize_text(text),
          speaker_wav=reader.reference_path,
          language=language,
          file_path=filename,
          **kwargs
      )
      filenames.append(filename)
    return filenames

def normalize_text(text: str) -> str:
  # Remove non-alphanumeric characters
  text = re.sub(r"[^a-zA-Z0-9\s\.\,\!\?\'\-\(\)\:]", "", text)
  # Move isolated punctuation to attach to previous word if possible
  text = re.sub(r'(\w)\s+([.!?,\'-]+)(?=\s|$)', r'\1\2', text)  # "word !" -> "word!"
  # Remove any remaining standalone punctuation
  text = re.sub(r'^([.!?,\'-]+)(?=\s|$)', '', text)    # Remove punctuation at start
  text = re.sub(r'\s+([.!?,\'-]+)(?=\s|$)', '', text)  # Remove any remaining isolated punctuation
  # Clean up any resulting multiple spaces
  text = re.sub(r'\s+', ' ', text)
  # Trim leading/trailing whitespace
  text = text.strip()
  return text
