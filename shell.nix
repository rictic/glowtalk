{ pkgs }:

pkgs.mkShell {
  buildInputs = [
    pkgs.python311
    pkgs.ffmpeg
    pkgs.nodejs_20
    pkgs.nodePackages.esbuild
  ] ++ (
    if pkgs.stdenv.isDarwin then [
      # Add macOS specific dependencies here if any, beyond pyobjc
    ] else [
      # Add Linux specific dependencies here if any
    ]
  );

  # Propagated build inputs are for dependencies that should be available to projects using this shell.
  # For a development shell, you might list most things in buildInputs directly,
  # or use propagatedBuildInputs if you intend for other derivations to inherit them via this shell.
  # For clarity and direct availability in the shell, buildInputs is often sufficient.
  # However, the original request had them as propagated, so keeping that structure.
  propagatedBuildInputs = with pkgs.python311Packages; [
    tts
    beautifulsoup4
    sqlalchemy
    pysbd
    alembic
    fastapi
    uvicorn
    pydantic
    python-multipart
    httpx
    ffmpeg-python
    pydub
    sse-starlette
    pytest
    pytest-watch
    pytest-httpx
    pytest-asyncio
  ] ++ (if pkgs.stdenv.isDarwin then [ pkgs.python311Packages.pyobjc ] else [ ]);

  shellHook = ''
    # The PYTHONPATH might need adjustment depending on how packages are installed/available.
    # For a development shell, often you're working directly in the source directory,
    # and Python's import system handles local packages.
    # If using `pip install -e .` or similar, PYTHONPATH modification might not be needed,
    # or might be set up differently by those tools.
    # For now, keeping a generic PYTHONPATH that includes a potential src directory.
    export PYTHONPATH="${pkgs.python311Packages.python.sitePackages}:${pkgs.python311Packages.makePythonPath [ ./src ]}"
    echo "Nix shell is ready."
    echo "Available commands: python, node, esbuild, pytest"
  '';
}
