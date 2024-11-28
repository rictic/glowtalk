from pydub import AudioSegment
from pathlib import Path

def combine_wav_to_mp3(wav_files: list[Path], output_mp3_path: Path):
    # Start with the first file
    combined = AudioSegment.from_wav(wav_files[0])

    # Add all other files
    for wav_file in wav_files[1:]:
        audio = AudioSegment.from_wav(wav_file)
        combined += audio

    # Export as MP3
    combined.export(output_mp3_path, format="mp3")

if __name__ == "__main__":
    combine_wav_to_mp3([Path("outputs/output 42.wav"), Path("outputs/output 43.wav")], Path("output.mp3"))
