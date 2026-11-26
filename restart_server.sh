#!/bin/bash
# 重启 odele-ctf Web 控制台（前后端分离版）
# 杀掉旧的 server 进程 + 重新拉起，日志写到 /tmp/odele-server.log
set -e
cd "$(dirname "$0")"

# also match the pre-rename "server.app" module so an old process can't hold the port
pkill -f "python.*-m (server|backend)\.app" 2>/dev/null || true
sleep 1

nohup .venv/bin/python -m backend.app >/tmp/odele-server.log 2>&1 &
echo "Web 控制台已启动：http://127.0.0.1:8765"
echo "pid: $!    日志: /tmp/odele-server.log"
