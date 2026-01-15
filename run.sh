#!/bin/bash
# 啟動機械手臂訂單管理系統
# 同時啟動主應用和遠端控制台

cd "$(dirname "$0")"

# 啟用虛擬環境
source .venv/bin/activate

echo "🚀 啟動機械手臂訂單管理系統..."
echo ""
echo "📺 主應用 (監控): http://localhost:1870"
echo "📡 API 端點:      http://localhost:1872"
echo "🎮 遠端控制:      http://localhost:1871"
echo ""

# 在背景啟動主應用
python webcam_app.py &
MAIN_PID=$!
echo "✅ 主應用 PID: $MAIN_PID"

# 等待主應用啟動
sleep 3

# 在背景啟動遠端控制
python remote_control.py &
REMOTE_PID=$!
echo "✅ 遠端控制 PID: $REMOTE_PID"

echo ""
echo "按 Ctrl+C 停止所有應用..."

# 捕捉 Ctrl+C 並關閉所有程序
trap "echo '正在關閉...'; kill $MAIN_PID $REMOTE_PID 2>/dev/null; exit" SIGINT SIGTERM

# 等待程序結束
wait
