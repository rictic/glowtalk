import pysbd

segmenter = pysbd.Segmenter(language="en", clean=True)

def segment(text: str) -> list[str]:
  return segmenter.segment(text)
