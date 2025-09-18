@echo off
echo ========================================
echo    Локальный AI Ассистент
echo ========================================
echo.

echo [1/3] Запуск Ollama сервера...
start "Ollama Server" cmd /k "& "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve"

echo [2/3] Ожидание запуска Ollama (10 секунд)...
timeout /t 10 /nobreak >nul

echo [3/3] Запуск веб-интерфейса...
echo.
echo Веб-интерфейс будет доступен по адресам:
echo - Локально: http://localhost:5000
echo - Из сети: http://[ВАШ_IP]:5000
echo.
echo Для подключения с других устройств используйте IP адрес этого компьютера
echo.

python app.py

pause
