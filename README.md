# GlowTalk

Generate audiobooks for glowfics

## Installation

```bash
uv pip install glowtalk
```

## Usage

```bash
glowtalk
```

## Development with Nix

Nix can be used to provide a consistent and reproducible development environment with all necessary dependencies.

**1. Install Nix:**

If you don't have Nix installed, follow the official installation guide: [Nix Installation Guide](https://nixos.org/download.html).

**2. Enter the Development Shell:**

Once Nix is installed, navigate to the project's root directory and run:

```bash
nix develop
```
This command will build the environment if it's the first time or if dependencies have changed, and then drop you into a shell with all project dependencies available. If you have direnv installed and configured for Nix, you can often just `cd` into the directory.

**3. Using the Environment:**

Inside the Nix shell, the following tools (and others specified in `shell.nix`) are available in your PATH:
*   `python` (version 3.11)
*   `pytest`
*   `node` (version 20.x)
*   `esbuild`

**4. Running Tests:**

To run the Python test suite:
```bash
pytest
```

**5. Building the Project:**

To build the entire Python application using Nix (this will also build the frontend assets as part of the process):
```bash
nix build .#package
```
The result will be a symlink named `result` in the project's root directory (e.g., `./result/bin/glowtalk`).

**6. Frontend Development:**

The Nix environment also provides `node` and `esbuild` for frontend development. If you need to work on the frontend interactively (e.g., with live reloading), you can still use the npm scripts from within the Nix shell:
```bash
cd glowtalk/static
# npm ci # Not strictly needed if esbuild is globally available via Nix
npm run watch
```
Alternatively, you can invoke `esbuild` directly as it's available in the Nix shell. The `npm run build` script for the frontend is effectively handled by the main `nix build .#package` command.

To install development dependencies and build the package:

```bash
uv venv
source .venv/bin/activate
uv pip install hatch
uv pip install -e .
```

## Frontend dev

We have a web based frontend. We check in a built version of the frontend so you only need to set up this environment if you want to make changes to it.

```bash

cd glowtalk/static # frontend is in here

# install deps. only need to run this once
npm ci

# Then run either:

npm run watch # starts a server that rebuilds on changes. run while developing

# Or:

# builds in prod mode, producing an optimized bundle. run before deploying
# to make the site load and run faster
npm run build
```
