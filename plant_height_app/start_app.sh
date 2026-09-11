#!/usr/bin/env sh
set -eu
APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_DIR=$(dirname "$APP_DIR")
ENV_DIR="$REPO_DIR/.venv-plant-height"
if [ ! -x "$ENV_DIR/bin/python" ]; then
  python3 -m venv "$ENV_DIR"
fi
"$ENV_DIR/bin/python" -m pip install -r "$APP_DIR/requirements.txt"
"$ENV_DIR/bin/python" -m streamlit run "$APP_DIR/app.py"
