#!/bin/bash
# 备考刷题 · 手机访问服务
# 双击运行后，手机连同一个 Wi-Fi，用 Safari/Chrome 打开终端里显示的网址即可。
# 首次打开后建议「添加到主屏幕」，之后离线也能刷题。
PORT=8642
DIR="$HOME/Desktop/启动器/备考刷题_v1"

IP=$(ipconfig getifaddr en0 2>/dev/null)
[ -z "$IP" ] && IP=$(ipconfig getifaddr en1 2>/dev/null)
[ -z "$IP" ] && IP="127.0.0.1"

URL="http://$IP:$PORT/"
echo ""
echo "  ┌─────────────────────────────────────────┐"
echo "  │  备考刷题 · 手机访问服务已启动           │"
echo "  │                                         │"
printf "  │  手机浏览器打开：  %s\n" "$URL"
echo "  │  （手机与 Mac 需连同一个 Wi-Fi）         │"
echo "  │                                         │"
echo "  │  打开后点「添加到主屏幕」→ 离线可用      │"
echo "  │  停止服务：在本窗口按 Ctrl+C             │"
echo "  └─────────────────────────────────────────┘"
echo ""
sleep 1
open "http://localhost:$PORT/"
cd "$DIR" && python3 -m http.server $PORT
