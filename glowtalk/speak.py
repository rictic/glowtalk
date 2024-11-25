import re
import os
from pathlib import Path
import tempfile
import torch
from TTS.api import TTS
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
  def __init__(self, model: str):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
      print("pytorch isn't happy with your cuda so this will be slower")

    if model != "tts_models/multilingual/multi-dataset/xtts_v2":
        raise ValueError(f"Unsupported model: {model}")
    self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)

  def speak(self, text: str, speaker_wav: Path, language="en", **kwargs) -> list[Path]:
    filename = get_unique_filename()
    self.tts.tts_to_file(
        text=text,
        speaker_wav=speaker_wav,
        language=language,
        file_path=filename,
        **kwargs
    )
    return filename

