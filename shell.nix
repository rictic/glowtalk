{ pkgs }:

pkgs.mkShell {
  buildInputs =
    [
      pkgs.python311
      pkgs.python311Packages.pip
      pkgs.python311Packages.virtualenv
      pkgs.ffmpeg
      pkgs.nodejs_20
      pkgs.esbuild
    ]
    ++ (
      if pkgs.stdenv.isDarwin then
        [
          # Add macOS specific dependencies here if any
        ]
      else
        [
          # Add Linux specific dependencies here if any
          pkgs.espeakng # TTS backend for Linux
          pkgs.alsaLib # Audio support for Linux
        ]
    );

  # Include commonly available Python packages from nixpkgs
  propagatedBuildInputs = with pkgs.python311Packages; [
    # Core packages that are available in nixpkgs
    beautifulsoup4
    sqlalchemy
    alembic
    fastapi
    uvicorn
    pydantic
    httpx
    pydub
    pytest
    pytest-asyncio
    # Note: some packages like tts, pysbd, python-multipart, ffmpeg-python, sse-starlette, pyobjc
    # may need to be installed via pip in the development environment
  ];

  shellHook = ''
    echo "Glowtalk development environment activated!"
    echo "Available commands: python, pip, node, esbuild, pytest"
    echo ""
    echo "Setting up Python virtual environment..."
    if [ ! -d ".venv-nix" ]; then
      python -m venv .venv-nix
      echo "Created .venv-nix virtual environment"
    fi
    source .venv-nix/bin/activate
    echo "Activated .venv-nix virtual environment"
    echo ""
    
    # Check if the project is installed in editable mode
    if ! pip show glowtalk &>/dev/null; then
      echo "Installing project in editable mode..."
      pip install -e .
      echo "Project installed successfully!"
    else
      echo "Project already installed in editable mode"
    fi
    
    # Install pytest in the virtual environment to ensure it uses the right Python path
    if ! pip show pytest &>/dev/null; then
      echo "Installing pytest in virtual environment..."
      pip install pytest pytest-asyncio
      echo "Pytest installed successfully!"
    fi
    
    echo ""
    echo "To install additional Python dependencies:"
    echo "  pip install tts pysbd python-multipart ffmpeg-python sse-starlette"
    echo ""
    echo "To run the application:"
    echo "  python -m glowtalk --help"
    echo ""
    echo "To run tests (use the virtual environment's pytest):"
    echo "  python -m pytest"
  '';
}
