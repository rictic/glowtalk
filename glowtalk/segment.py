import re
import pysbd

segmenter = pysbd.Segmenter(language="en", clean=True)

def segment(text: str) -> list[str]:
  return [normalize_text(seg) for seg in segmenter.segment(text)]


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
