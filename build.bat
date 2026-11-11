@echo off
REM Gera dist\auto_seta.exe (launcher com janela; não precisa de Python no PC dos amigos)
python -m pip install --upgrade pyinstaller mss numpy pillow
python -m PyInstaller --onefile --windowed --uac-admin --name auto_seta --clean --noconfirm launcher.py
copy /Y LEIA-ME.txt dist\LEIA-ME.txt >nul
echo.
echo Pronto: dist\auto_seta.exe
pause
