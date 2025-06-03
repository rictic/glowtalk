{ lib
, stdenv
, buildPythonPackage
, fetchPypi
, cython
, numpy
, scipy
, torch
, torchaudio
, soundfile
, librosa
, scikit-learn
, numba
, inflect
, tqdm
, anyascii
, pyyaml
, fsspec
, aiohttp
, packaging
, flask
, pysbd
, umap-learn
, pandas
, matplotlib
, trainer
, coqpit
, jieba
, pypinyin
, hangul_romanize
, gruut
, jamo
, nltk
, g2pkk
, bangla
, bnnumerizer
, bnunicodenormalizer
, einops
, transformers
, encodec
, unidecode
, num2words
, spacy
, ffmpeg
, sox
, espeak
}:

buildPythonPackage rec {
  pname = "TTS";
  version = "0.22.0";
  format = "setuptools";

  src = fetchPypi {
    inherit pname version;
    hash = "sha256-uREZ2n/yrns9rnMo7fmvTbO0jEDrTOFdEe2PXum9cIY=";
  };

  nativeBuildInputs = [
    cython
  ];

  buildInputs = [
    ffmpeg
    sox
    espeak
  ];

  propagatedBuildInputs = [
    # Core dependencies
    numpy
    cython
    scipy
    torch
    torchaudio
    soundfile
    librosa
    scikit-learn
    numba
    inflect
    tqdm
    anyascii
    pyyaml
    fsspec
    aiohttp
    packaging
    # Examples
    flask
    # Inference
    pysbd
    # Notebooks (optional but commonly used)
    umap-learn
    pandas
    # Training
    matplotlib
    # Coqui stack
    trainer
    coqpit
    # Basic language support
    jieba
    pypinyin
    gruut
    jamo
    nltk
    # Model-specific deps
    einops
    transformers
    encodec
    unidecode
    num2words
    spacy
    # Include hangul_romanize and optional deps when available
    hangul_romanize
  ] ++ lib.optionals (!stdenv.isDarwin) [
    # These might have issues on Darwin
    bangla
    bnnumerizer
    bnunicodenormalizer
    g2pkk
  ];

  # Tests require model downloads and additional setup
  doCheck = false;

  pythonImportsCheck = [
    "TTS"
  ];

  meta = with lib; {
    description = "Deep learning for Text to Speech by Coqui";
    homepage = "https://github.com/coqui-ai/TTS";
    license = licenses.mpl20;
    maintainers = with maintainers; [ ];
  };
}
