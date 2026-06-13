@echo off
echo ╔══════════════════════════════════╗
echo ║     盘古AI 一键启动              ║
echo ╚══════════════════════════════════╝
echo.
echo 启动 Python 引擎 (后台)...
start "盘古Python引擎" python pangu_bridge.py --port 5100
timeout /t 3 /nobreak >nul

echo 启动 Java 骨架...
cd backend-java
mvn spring-boot:run

echo.
echo 盘古已启动: Java→http://localhost:8080  Python→http://localhost:5100
pause
