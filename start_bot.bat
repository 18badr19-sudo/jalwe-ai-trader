@echo off
title Autonomous Institutional Trading Bot
:loop
echo ==========================================
echo Starting Trading Bot... [%date% %time%]
echo ==========================================
python bot.py
echo ⚠️ Bot stopped or crashed! Restarting in 10 seconds...
timeout /t 10
goto loop