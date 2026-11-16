#!/bin/bash
# 重启 odele-ctf GUI（杀掉旧的 + 清理 worker 子进程 + 重新拉起）
set -e
cd "$(dirname "$0")"

pkill -f "gui.launch" 2>/dev/null || true
pkill -f "from multiprocessing.spawn import spawn_main" 2>/dev/null || true
pkill -f "from multiprocessing.resource_tracker import main" 2>/dev/null || true
sleep 1

nohup .venv/bin/python -m gui.launch >/tmp/odele-gui.log 2>&1 &
echo "GUI restarted (pid $!), log: /tmp/odele-gui.log"
