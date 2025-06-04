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

        # Override problematic packages to disable tests
        overriddenPythonPackages = pkgs.python311Packages.override {
          overrides = final: prev: {
            # Disable tests for packages that have known failures
            portalocker = prev.portalocker.overridePythonAttrs (old: {
              doCheck = false;
            });

            # Add other problematic packages as needed
            pyarrow = prev.pyarrow.overridePythonAttrs (old: {
              doCheck = false;
            });

            # Fix pytest-doctestplus test failure that blocks the entire build
            pytest-doctestplus = prev.pytest-doctestplus.overridePythonAttrs (old: {
              doCheck = false;
            });

            # Fix mirakuru test failures that block other packages
            mirakuru = prev.mirakuru.overridePythonAttrs (old: {
              doCheck = false;
            });

            # Fix sqlframe NumPy 2.0 compatibility issues
            sqlframe = prev.sqlframe.overridePythonAttrs (old: {
              doCheck = false;
            });
          };
        };

        # Import custom packages
        customPythonPackages = import ./packages {
          inherit pkgs;
          pythonPackages = overriddenPythonPackages;
        };

        # All Python dependencies from pyproject.toml, managed by Nix
        pythonDeps =
          with overriddenPythonPackages;
          [
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
            requests # needed by glowfic_scraper
            attrs # needed by tests

            # Development dependencies
            pytest
            pytest-httpx
            pytest-watch
            pytest-asyncio
          ]
          ++ [
            # Custom packages
            customPythonPackages.TTS
          ]
          ++ pkgs.lib.optionals pkgs.stdenv.isDarwin [
            # macOS-specific dependencies would go here
            # Note: pyobjc is not available in nixpkgs, so this might need a custom package
          ];

        # System dependencies
        systemDeps =
          [
            pkgs.ffmpeg
            pkgs.nodejs_20
            pkgs.espeak # Required for TTS
            pkgs.sox # Audio processing for TTS
          ]
          ++ (
            if pkgs.stdenv.isDarwin then
              [ ]
            else
              [
                pkgs.espeak-ng # TTS backend for Linux
                pkgs.alsa-lib # Audio support for Linux
              ]
          );

        # Frontend build
        frontendBuild = pkgs.buildNpmPackage {
          pname = "glowtalk-frontend";
          version = "0.1.0";
          src = ./glowtalk/static;

          npmDepsHash = "sha256-cIQnd58zkN55avY0xkraiDjboIknky1fX6mV3XQJdeE=";
          npmBuildScript = "build";

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
          format = "pyproject";

          nativeBuildInputs = with pkgs.python311Packages; [ hatchling ];
          buildInputs = systemDeps;
          propagatedBuildInputs = pythonDeps;

          # Enable tests during build
          doCheck = true;
          nativeCheckInputs = with overriddenPythonPackages; [
            pytest
            pytest-httpx
            pytest-asyncio
          ];

          checkPhase = ''
            runHook preCheck
            # Run pytest with verbose output
            pytest -v
            runHook postCheck
          '';

          postInstall = ''
            target_static_dir="$out/lib/python3.11/site-packages/glowtalk/static"
            mkdir -p $target_static_dir
            cp -R ${frontendBuild}/static/dist $target_static_dir/
          '';

          meta = with pkgs.lib; {
            description = "Generate audiobooks for Glowfics";
            license = licenses.mit;
          };
        };

        # Development shell - purely Nix-based
        devShell = pkgs.mkShell {
          buildInputs =
            [
              pkgs.python311
            ]
            ++ systemDeps
            ++ pythonDeps;

          shellHook = ''
            echo "🎤 Glowtalk development environment activated!"
            echo ""
            echo "📋 Available commands:"
            echo "  python -m glowtalk --help    # Run the application"
            echo "  pytest                       # Run tests"
            echo "  cd glowtalk/static && npm run build  # Build frontend"
            echo ""
            echo "🔧 Development tools:"
            echo "  python --version             # Python $(python --version | cut -d' ' -f2)"
            echo "  python -c 'import glowtalk; print(\"glowtalk module available\")'  # Test imports"
            echo "  python -c 'import TTS; print(\"TTS module available\")'  # Test TTS"
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
