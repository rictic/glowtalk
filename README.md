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
