@echo off
setlocal

:: ==============================================
:: 🚀 SERVIDOR DEL CONSULTORIO
:: ==============================================

:: ⚙ Configuración UTF-8
chcp 65001 >nul
set PYTHONIOENCODING=utf-8

:: 📝 Logs
if exist django.log del django.log
if exist debug_log.txt del debug_log.txt
echo ==== INICIO DEL SCRIPT (%date% %time%) ==== > debug_log.txt

:: ✅ 1) INICIAR MYSQL CON XAMPP EN SEGUNDO PLANO
echo 🔄 Iniciando MySQL desde XAMPP... >> debug_log.txt
start "" /min cmd /c "cd /d C:\xampp && call mysql_start.bat"

:: ✅ 2) INICIAR DJANGO EN SEGUNDO PLANO
echo 🔄 Iniciando Django... >> debug_log.txt
if exist venv\Scripts\activate (
    echo ✔ Entorno virtual encontrado. >> debug_log.txt
    start "" /min cmd /c "call venv\Scripts\activate && python manage.py runserver >> django.log 2>&1"
) else (
    echo ⚠ No se encontró el entorno virtual 'venv'. Ejecutando con Python global. >> debug_log.txt
    start "" /min cmd /c "python manage.py runserver >> django.log 2>&1"
)

:: ✅ 3) ESPERAR HASTA QUE DJANGO ARRANQUE
echo ⏳ Esperando a que Django esté listo... >> debug_log.txt
:espera
timeout /t 1 >nul
findstr /C:"Starting development server at http://127.0.0.1:8000/" django.log >nul 2>&1
if errorlevel 1 goto espera

echo ==== FIN DEL SCRIPT (%date% %time%) ==== >> debug_log.txt
echo ✅ SERVIDOR DEL CONSULTORIO INICIADO
exit
