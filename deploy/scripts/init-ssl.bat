@echo off
REM First-time Let's Encrypt certificate issuance (Windows dev machine helper).
REM Run this ON THE UBUNTU SERVER via Git Bash or WSL, not native Windows cmd.

echo This script is intended for Linux. On the server run:
echo   chmod +x deploy/scripts/init-ssl.sh
echo   ./deploy/scripts/init-ssl.sh
exit /b 1
