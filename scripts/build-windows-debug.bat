@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "PROJECT_DIR=%%~fI"
set "VENV_PYTHON=%PROJECT_DIR%\venv\Scripts\python.exe"
set "DIST_DIR=%PROJECT_DIR%\dist"
set "APP_NAME=HouSign-Debug"
set "APP_DIR=%DIST_DIR%\%APP_NAME%"

echo ========================================
echo     HouSign Windows Debug Build
echo ========================================
echo.

if not exist "%VENV_PYTHON%" (
    echo ERROR: Virtual environment not found at "%VENV_PYTHON%"
    echo Create it first with:
    echo   py -3 -m venv venv
    echo   venv\Scripts\python.exe -m pip install -r requirements.txt
    exit /b 1
)

echo [1/4] Installing Python dependencies...
"%VENV_PYTHON%" -m pip install -r "%PROJECT_DIR%\requirements.txt"
if errorlevel 1 exit /b 1
echo.

echo [2/4] Cleaning previous build output...
if exist "%PROJECT_DIR%\build" rmdir /s /q "%PROJECT_DIR%\build"
if exist "%APP_DIR%" rmdir /s /q "%APP_DIR%"
echo.

echo [3/5] Building console version with PyInstaller...
"%VENV_PYTHON%" -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --console ^
  --onedir ^
  --name "%APP_NAME%" ^
  --icon "%PROJECT_DIR%\logo.ico" ^
  --collect-all flet ^
  --collect-all mediapipe ^
  --hidden-import pystray ^
  --hidden-import pyaudio ^
  --hidden-import websockets.sync.client ^
  --hidden-import PIL ^
  --add-data "%PROJECT_DIR%\models;models" ^
  --add-data "%PROJECT_DIR%\ha_gestures\sound;ha_gestures\sound" ^
  --add-data "%PROJECT_DIR%\settings.json;." ^
  --add-data "%PROJECT_DIR%\gestures.yaml;." ^
  --add-data "%PROJECT_DIR%\gesture_bindings.json;." ^
  --add-data "%PROJECT_DIR%\logo.png;." ^
  --add-data "%PROJECT_DIR%\logo.ico;." ^
  "%PROJECT_DIR%\ha_gestures\app.py"
if errorlevel 1 exit /b 1
echo.

echo [4/5] Copying runtime assets next to the executable...
if not exist "%APP_DIR%\models" mkdir "%APP_DIR%\models"
copy /Y "%PROJECT_DIR%\settings.json" "%APP_DIR%\settings.json" >nul
copy /Y "%PROJECT_DIR%\gestures.yaml" "%APP_DIR%\gestures.yaml" >nul
copy /Y "%PROJECT_DIR%\gesture_bindings.json" "%APP_DIR%\gesture_bindings.json" >nul
copy /Y "%PROJECT_DIR%\logo.png" "%APP_DIR%\logo.png" >nul
copy /Y "%PROJECT_DIR%\logo.ico" "%APP_DIR%\logo.ico" >nul
copy /Y "%PROJECT_DIR%\models\hand_landmarker.task" "%APP_DIR%\models\hand_landmarker.task" >nul
echo.

echo [5/5] Optional installer build...
set "INNO_SCRIPT=%PROJECT_DIR%\scripts\setup.iss"
set "ISCC_EXE=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "%ISCC_EXE%" (
    "%ISCC_EXE%" "%INNO_SCRIPT%" ^
      /DAppName="HouSign-Debug" ^
      /DAppExeName="HouSign-Debug.exe" ^
      /DOutputBaseFilename="HouSign-Debug-Setup" ^
      /DSourceDir="%DIST_DIR%\HouSign-Debug"
) else (
    echo Inno Setup not found at "%ISCC_EXE%", skipping installer.
)

echo.
echo Debug build output:
echo   %APP_DIR%
if exist "%DIST_DIR%\installer\HouSign-Debug-Setup.exe" echo   %DIST_DIR%\installer\HouSign-Debug-Setup.exe
echo.
echo Run it from Command Prompt to see logs:
echo   "%APP_DIR%\%APP_NAME%.exe" settings
echo   "%APP_DIR%\%APP_NAME%.exe" runtime
echo   "%APP_DIR%\%APP_NAME%.exe" preview
echo.
endlocal
