@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ==================================================
echo   SUBCAST STUDIO 실행 준비 중...
echo ==================================================

where ffmpeg >nul 2>nul
if %errorlevel% neq 0 (
    echo [안내] FFmpeg가 설치되어 있지 않습니다. winget으로 설치를 시도합니다...
    winget install -e --id Gyan.FFmpeg
)

if not exist ".venv" (
    echo 초기 실행 환경을 구성하고 있습니다 ^(최초 1회^)...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

echo 브라우저에서 SUBCAST STUDIO ^(http://127.0.0.1:8765^) 를 엽니다...
python server.py
pause
