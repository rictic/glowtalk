import soundfile as sf
import subprocess
from pathlib import Path
from typing import List, Iterator
import numpy as np
import itertools

def stream_wav_chunks(wav_files: Iterator[Path], chunk_size: int = 8192) -> Iterator[np.ndarray]:
    """Stream audio data from WAV files in chunks."""
    for wav_file in wav_files:
        with sf.SoundFile(wav_file) as f:
            while True:
                chunk = f.read(chunk_size)
                if not len(chunk):
                    break
                yield chunk

def combine_wav_to_mp3(wav_files: Iterator[Path], output_mp3_path: Path) -> None:
    """Combine multiple WAV files into a single MP3 file using streaming."""
    if not wav_files:
        raise ValueError("No input files provided")
    # Get audio properties from first file
    first_file = next(wav_files)
    if first_file is None:
        raise ValueError(f"No input files provided to generate {output_mp3_path}")
    with sf.SoundFile(first_file) as f:
        sample_rate = f.samplerate
        channels = f.channels

    # Set up FFmpeg process for MP3 encoding
    cmd = [
        'ffmpeg',
        '-y',                    # Overwrite output file if it exists
        '-f', 'f32le',          # Input format (32-bit float PCM)
        '-ar', str(sample_rate), # Sample rate
        '-ac', str(channels),    # Number of channels
        '-i', '-',              # Read from stdin
        '-c:a', 'libmp3lame',   # MP3 encoder
        '-q:a', '2',            # Quality setting (2 is high quality, 0 is highest)
        str(output_mp3_path)
    ]

    # Start FFmpeg process
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    try:
        # Stream chunks to FFmpeg
        for chunk in stream_wav_chunks(itertools.chain([first_file],    wav_files)):
            chunk = chunk.astype(np.float32)
            process.stdin.write(chunk.tobytes())

        # Properly close stdin and wait for process to complete
        process.stdin.close()
        stderr = process.stderr.read()
        process.wait()

        if process.returncode != 0:
            raise RuntimeError(f"FFmpeg error: {stderr.decode()}")

    except Exception as e:
        # Make sure to terminate the process if anything goes wrong
        process.terminate()
        process.wait(timeout=5)  # Give it 5 seconds to shut down gracefully
        raise e

if __name__ == "__main__":
    def gen():
        yield Path("outputs/output 42.wav")
        yield Path("outputs/output 43.wav")
    combine_wav_to_mp3(
        gen(),
        Path("output.mp3")
    )
