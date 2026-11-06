#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

echo "=================================================="
echo "  SUBCAST STUDIO 실행 준비 중..."
echo "=================================================="

# 1. Check FFmpeg
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "[안내] FFmpeg가 설치되어 있지 않습니다."
  if command -v brew >/dev/null 2>&1; then
    echo "Homebrew를 통해 FFmpeg를 자동 설치합니다..."
    brew install ffmpeg
  else
    echo "터미널에서 'brew install ffmpeg'를 먼저 실행해 주세요."
    read -p "엔터 키를 누르면 종료합니다..."
    exit 1
  fi
fi

# 2. Setup Python Virtual Environment if missing
PYTHON_BIN=""
for candidate in python3.13 python3.12 python3.11 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v "$candidate")"
    break
  fi
done

if [ ! -d ".venv" ]; then
  echo "초기 실행 환경을 구성하고 있습니다 (최초 1회, 약 30초 소요)..."
  "$PYTHON_BIN" -m venv .venv
  ./.venv/bin/pip install --upgrade pip
  ./.venv/bin/pip install -r requirements.txt
fi

echo "브라우저에서 SUBCAST STUDIO (http://127.0.0.1:8765) 를 엽니다..."
exec ./.venv/bin/python server.py
