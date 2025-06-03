{
  description = "Glowtalk - Generate audiobooks for Glowfics";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};

        # Common Python packages available in nixpkgs
        availablePythonPkgs = with pkgs.python311Packages; [
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
        ];

        # System dependencies
        systemDeps =
          [
            pkgs.ffmpeg
            pkgs.nodejs_20
            pkgs.esbuild
          ]
          ++ (
            if pkgs.stdenv.isDarwin then
              [ ]
            else
              [
                pkgs.espeakng # TTS backend for Linux
                pkgs.alsaLib # Audio support for Linux
              ]
          );

        # Frontend build
        frontendBuild = pkgs.stdenv.mkDerivation {
          pname = "glowtalk-frontend";
          version = "0.1.0";
          src = ./glowtalk/static;

          buildInputs = [
            pkgs.nodejs_20
            pkgs.esbuild
          ];

          buildPhase = ''
            runHook preBuild
            esbuild src/main.tsx --bundle --outfile=dist/bundle.js --sourcemap --minify --define:process.env.NODE_ENV=\"production\"
            mkdir -p dist
            runHook postBuild
          '';

          installPhase = ''
            runHook preInstall
            mkdir -p $out/static
            cp -R dist $out/static/
            runHook postInstall
          '';
        };

        # Main package
        glowtalkPackage = pkgs.python311Packages.buildPythonApplication {
          pname = "glowtalk";
          version = "0.1.0";
          src = ./.;

          nativeBuildInputs = with pkgs.python311Packages; [ hatchling ];
          buildInputs = systemDeps;
          propagatedBuildInputs = availablePythonPkgs;

          postInstall = ''
            target_static_dir="$out/lib/python3.11/site-packages/glowtalk/static"
            mkdir -p $target_static_dir
            cp -R ${frontendBuild}/static/dist $target_static_dir/
          '';

          # Skip tests during build since some dependencies aren't available
          doCheck = false;

          meta = with pkgs.lib; {
            description = "Generate audiobooks for Glowfics";
            license = licenses.mit;
          };
        };

        # Development shell
        devShell = pkgs.mkShell {
          buildInputs = [
            pkgs.python311
            pkgs.python311Packages.pip
            pkgs.python311Packages.virtualenv
          ] ++ systemDeps;

          propagatedBuildInputs = availablePythonPkgs;

          shellHook = ''
            echo "🎤 Glowtalk development environment activated!"
            echo ""

            # Set up Python virtual environment
            if [ ! -d ".venv-nix" ]; then
              echo "Creating Python virtual environment..."
              python -m venv .venv-nix
            fi

            source .venv-nix/bin/activate
            echo "✅ Virtual environment activated"

            # Install project in editable mode
            if ! pip show glowtalk &>/dev/null; then
              echo "Installing project in editable mode..."
              pip install -e .
            fi

            echo ""
            echo "📋 Available commands:"
            echo "  python -m glowtalk --help    # Run the application"
            echo "  python -m pytest            # Run tests"
            echo "  cd glowtalk/static && npm run build  # Build frontend"
            echo ""
            echo "📦 Missing dependencies will be installed via pip automatically"
            echo "   when you run the application for the first time."
          '';
        };
      in
      {
        # Export the package
        packages.default = glowtalkPackage;
        packages.glowtalk = glowtalkPackage;

        # Development shell for `nix develop`
        devShells.default = devShell;

        # Apps for running the application
        apps.default = {
          type = "app";
          program = "${glowtalkPackage}/bin/glowtalk";
        };
      }
    );
}
