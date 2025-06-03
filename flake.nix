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
        
        # Import custom packages
        customPythonPackages = import ./packages { 
          inherit pkgs; 
          pythonPackages = pkgs.python311Packages;
        };

        # All Python dependencies from pyproject.toml, managed by Nix
        pythonDeps = with pkgs.python311Packages; [
          # Core dependencies from pyproject.toml
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
          
          # Development dependencies
          pytest
          pytest-httpx
          pytest-watch
          pytest-asyncio
        ] ++ [
          # Custom packages
          customPythonPackages.TTS
        ] ++ pkgs.lib.optionals pkgs.stdenv.isDarwin [
          # macOS-specific dependencies would go here
          # Note: pyobjc is not available in nixpkgs, so this might need a custom package
        ];

        # System dependencies
        systemDeps =
          [
            pkgs.ffmpeg
            pkgs.nodejs_20
            pkgs.esbuild
            pkgs.espeak # Required for TTS
            pkgs.sox # Audio processing for TTS
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
          propagatedBuildInputs = pythonDeps;

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

        # Development shell - purely Nix-based
        devShell = pkgs.mkShell {
          buildInputs = [
            pkgs.python311
          ] ++ systemDeps ++ pythonDeps;

          shellHook = ''
            echo "🎤 Glowtalk development environment activated!"
            echo ""
            echo "✅ All dependencies managed by Nix"
            echo ""
            echo "📋 Available commands:"
            echo "  python -m glowtalk --help    # Run the application"
            echo "  python -m pytest            # Run tests"
            echo "  cd glowtalk/static && npm run build  # Build frontend"
            echo ""
            echo "🔧 Development tools:"
            echo "  python --version             # Python $(python --version | cut -d' ' -f2)"
            echo "  python -c 'import glowtalk; print(\"glowtalk module available\")'  # Test imports"
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
