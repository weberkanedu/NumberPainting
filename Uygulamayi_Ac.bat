@echo off
rem Piksel Studyo'yu acmak icin cift tikla. Ilk acilista gerekli kutuphaneleri kurar.
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python bulunamadi. python.org adresinden Python 3.10 veya ustunu kur,
  echo kurulumda "Add python.exe to PATH" kutusunu isaretle, sonra bu dosyayi tekrar ac.
  pause
  exit /b 1
)
python -c "import PIL, reportlab" 2>nul || (
  echo Gerekli kutuphaneler kuruluyor, bir kerelik...
  python -m pip install --user -r requirements.txt || (echo Kurulum basarisiz oldu. & pause & exit /b 1)
)
start "" pythonw sunucu.py
