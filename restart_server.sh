#!/bin/bash
# 重启 odele-ctf Web 控制台（前后端分离版）
# 杀掉所有旧后端进程（包括失败绑定残留的），再拉起一个；日志写 /tmp/odele-server.log
# 注意：macOS 的 pkill 不支持 (server|backend) 这种分组，这里用简化的多次匹配。
set -e
cd "$(dirname "$0")"

pkill -f "backend.app" 2>/dev/null || true
pkill -f "uvicorn.*backend" 2>/dev/null || true
pkill -f "server.app" 2>/dev/null || true

# 给优雅退出一点时间，残留的强制杀掉（旧版本可能忽略 SIGTERM）
for _ in $(seq 1 20); do
  if ! pgrep -f "backend.app" >/dev/null 2>&1; then
    break
  fi
  sleep 0.3
done
pkill -9 -f "backend.app" 2>/dev/null || true
sleep 1

nohup .venv/bin/python -m backend.app >/tmp/odele-server.log 2>&1 &
echo "Web 控制台已启动：http://127.0.0.1:8765"
echo "pid: $!    日志: /tmp/odele-server.log"
