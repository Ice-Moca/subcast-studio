#!/bin/zsh
cd "$(dirname "$0")"
echo "Starting SUBCAST STUDIO on http://127.0.0.1:8765 ..."
./.venv/bin/uvicorn server:app --host 127.0.0.1 --port 8765
