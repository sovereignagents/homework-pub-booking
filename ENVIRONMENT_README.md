# Frozen MacBook Environment

This repository has a known-clean working environment on a MacBook using Python 3.12.13 and the package versions pinned in `requirements.txt`.

`pyproject.toml` is not the source of truth for this environment because some module versions were adjusted after compatibility issues. Use `requirements.txt` to recreate the working setup.

## Recreate the Environment

From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The `requirements.txt` file was exported from the working local virtual environment with `uv pip freeze`. \
The editable project install is recorded as `-e .` so the checkout path can differ between machines.
