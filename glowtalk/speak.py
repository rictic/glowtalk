import re
import os
from pathlib import Path
import torch
from glowtalk import models


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

class Speaker:
  def __init__(self, model: models.SpeakerModel):
    from TTS.api import TTS
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
      print("pytorch isn't happy with your cuda so this will be slower")

    if model != models.SpeakerModel.XTTS_v2:
        raise ValueError(f"Unsupported model: {model}")
    self.tts = TTS(model.value).to(device)

  def speak(self, text: str, speaker_wav: Path, language="en", output_path = get_unique_filename(), **kwargs) -> Path:
    # Technically we should split the text into chunks of 250 characters or less,
    # because the model allegedly isn't able to handle longer text.
    # But I haven't noticed any issues with that yet.
    self.tts.tts_to_file(
      text=text,
      speaker_wav=speaker_wav,
      language=language,
      file_path=output_path,
      **kwargs
    )

    return output_path

