@echo off
title TTML Lyrics Studio - Installer
color 0A

echo ============================================================
echo   TTML Lyrics Studio ^& LRCGen - Installation Setup
echo ============================================================
echo.

cd /d "%~dp0"

REM 1. Check if Portable Embedded Python is present
if not exist "%~dp0python_embed\python.exe" goto :CHECK_SYS_PYTHON

echo [INFO] Portable Embedded Python detected: "%~dp0python_embed"
set "PY_CMD=%~dp0python_embed\python.exe"

if exist "%~dp0python_embed\Scripts\pip.exe" goto :INSTALL_DEPS
if not exist "%~dp0python_embed\get-pip.py" goto :INSTALL_DEPS

echo [INFO] Setting up pip for embedded Python...
"%PY_CMD%" "%~dp0python_embed\get-pip.py" --no-warn-script-location
goto :INSTALL_DEPS

:CHECK_SYS_PYTHON
REM 2. Check System Python
python --version >nul 2>&1
if errorlevel 1 goto :NO_PYTHON

for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo [INFO] Found: %%v

python -c "import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 13) else 1)" >nul 2>&1
if errorlevel 1 goto :WRONG_PYTHON

REM 3. Create venv if missing
if exist "%~dp0venv\Scripts\python.exe" goto :ACTIVATE_VENV

echo.
echo [1/5] Creating virtual Python environment in "%~dp0venv" ...
python -m venv "%~dp0venv"
if errorlevel 1 goto :VENV_ERROR

:ACTIVATE_VENV
echo [INFO] Activating virtual environment...
call "%~dp0venv\Scripts\activate.bat"
set "PY_CMD=%~dp0venv\Scripts\python.exe"

:INSTALL_DEPS
REM 4. Upgrade pip (non-fatal on Windows file locks)
echo.
echo [2/5] Updating pip...
"%PY_CMD%" -m pip install --upgrade pip --no-warn-script-location
if errorlevel 1 echo [INFO] Skipping pip upgrade, using current pip version...

REM 5. Detect GPU and Install PyTorch
echo.
echo [3/5] Checking hardware acceleration - NVIDIA GPU...
nvidia-smi >nul 2>&1
if errorlevel 1 goto :INSTALL_CPU

REM WhisperX 3.8.x pins torch~=2.8.0 / torchcodec<0.8 -> use the newest CUDA build of torch 2.8.0 (cu129)
echo [INFO] NVIDIA GPU detected! Installing PyTorch 2.8.0 with CUDA 12.9 for RTX 20xx/30xx/40xx/50xx...
"%PY_CMD%" -m pip install torch==2.8.0 torchvision==0.23.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu129 --no-warn-script-location
"%PY_CMD%" -m pip install "audio-separator>=0.24.0" --no-warn-script-location
set "USE_GPU=1"
goto :INSTALL_WHISPERX

:INSTALL_CPU
echo [INFO] No NVIDIA GPU detected or driver not in PATH. Installing Standard CPU PyTorch...
"%PY_CMD%" -m pip install torch==2.8.0 torchvision==0.23.0 torchaudio==2.8.0 --no-warn-script-location
"%PY_CMD%" -m pip install "audio-separator[cpu]>=0.24.0" --no-warn-script-location

:INSTALL_WHISPERX
REM 6. Install WhisperX into venv
echo.
echo [4/5] Installing WhisperX in venv...
"%PY_CMD%" -m pip install "whisperx>=3.1.1" --no-warn-script-location

REM 7. Install all dependencies from requirements.txt
echo.
echo [5/5] Installing all packages - FastAPI, Whisper, Pyphen, etc....
"%PY_CMD%" -m pip install -r "%~dp0requirements.txt" --no-warn-script-location
if errorlevel 1 goto :PIP_ERROR

REM onnxruntime-gpu 1.26.0 = last CUDA 12 build (1.27+ need CUDA 13). It shares its package dir with
REM the CPU "onnxruntime" that faster-whisper pulls in, so it must be (re)installed last to win.
if not "%USE_GPU%"=="1" goto :ORT_DONE
echo [INFO] Installing ONNX Runtime GPU 1.26.0 (CUDA 12)...
"%PY_CMD%" -m pip install --force-reinstall --no-deps "onnxruntime-gpu==1.26.0" --no-warn-script-location
if errorlevel 1 goto :PIP_ERROR
:ORT_DONE

REM 8. Portable shared FFmpeg 7.1 (torchcodec 0.7 loads FFmpeg 4-7 DLLs only)
echo.
echo [+] Installing portable FFmpeg 7.1 (shared) into "%~dp0ffmpeg" ...
if exist "%~dp0ffmpeg\bin\avcodec-61.dll" goto :FFMPEG_DONE
set "FF_URL=https://github.com/FFmpeg-Builds/FFmpeg-Builds/releases/download/autobuild-2026-07-31-14-10/ffmpeg-n7.1.5-12-g1fdbca85aa-win64-gpl-shared-7.1.zip"
set "FF_TMP=%TEMP%\lrcgen_ffmpeg"
if exist "%FF_TMP%" rmdir /s /q "%FF_TMP%"
mkdir "%FF_TMP%"
curl.exe -L -o "%FF_TMP%\ffmpeg.zip" "%FF_URL%"
if errorlevel 1 goto :FFMPEG_ERROR
tar -xf "%FF_TMP%\ffmpeg.zip" -C "%FF_TMP%"
if errorlevel 1 goto :FFMPEG_ERROR
if exist "%~dp0ffmpeg" rmdir /s /q "%~dp0ffmpeg"
for /d %%d in ("%FF_TMP%\ffmpeg-n7.1*") do move "%%d" "%~dp0ffmpeg" >nul
rmdir /s /q "%FF_TMP%"
if not exist "%~dp0ffmpeg\bin\avcodec-61.dll" goto :FFMPEG_ERROR
:FFMPEG_DONE
echo [INFO] FFmpeg ready: "%~dp0ffmpeg\bin"

REM 8. Verify installation
echo.
echo ============================================================
echo   Installation completed successfully!
echo ============================================================
echo.
echo Please start the studio by double-clicking: start.bat
echo When running start.bat, the browser will automatically open at:
echo http://127.0.0.1:8001
echo.
pause
exit /b 0

:NO_PYTHON
echo.
echo [ERROR] Python was not found!
echo Please install Python 3.10, 3.11, 3.12, or 3.13 from https://www.python.org/
echo IMPORTANT: Check the box "Add Python to PATH" during installation!
echo NOTE: Python 3.14+ is not yet supported by WhisperX / CTranslate2.
echo.
pause
exit /b 1

:WRONG_PYTHON
echo.
echo [WARNING / ERROR] Incompatible Python version detected!
echo LRCGen and WhisperX require Python 3.10 to 3.13.
echo Python 3.14 or newer is not yet supported by WhisperX and CTranslate2.
echo Please install Python 3.10 to 3.13.
echo.
pause
exit /b 1

:VENV_ERROR
echo.
echo [ERROR] Could not create virtual environment (venv).
echo.
pause
exit /b 1

:FFMPEG_ERROR
echo.
echo [ERROR] Could not install portable FFmpeg 7.1.
echo Download a "win64-gpl-shared-7.1" zip from https://github.com/FFmpeg-Builds/FFmpeg-Builds/releases
echo and extract it so that "%~dp0ffmpeg\bin\avcodec-61.dll" exists.
echo.
pause
exit /b 1

:PIP_ERROR
echo.
echo [ERROR] An error occurred while installing packages.
echo Please check the error messages above.
echo.
pause
exit /b 1
