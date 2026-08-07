# 🐍 Python JSON-RPC Daemon

This is the local AI and CAD orchestration backend. It runs as a child process of the Tauri application.

## Local Development Setup

We strictly use [uv](https://github.com/astral-sh/uv) for Python environment and dependency management because it is extremely fast and ensures deterministic cross-platform builds.

**1. Install uv**
(Follow official docs, or run `curl -LsSf https://astral.sh/uv/install.sh | sh`)

**2. Create the Virtual Environment**
Run this from inside the `services/python-daemon` directory:
```bash
uv venv
```

**3. Activate the Environment**
* Mac/Linux: `source .venv/bin/activate`
* Windows: `.venv\Scripts\activate`

**4. Install Dependencies & Run Tests**
```bash
uv pip install -r requirements.txt
python -m unittest discover tests/
```