#!/bin/bash
# 备考刷题 · 网页版（公网网址）
# 双击运行 → 自动生成 https 公网网址 + 弹出二维码，手机扫码即可打开
# 注意：网址每次运行都会变化；本窗口关闭 / Mac 关机后网页失效
# 停止：在本窗口按 Ctrl+C

DIR="$HOME/Desktop/启动器/备考刷题_v1"
PORT=8642
LOG=/tmp/bk_web_tunnel.log
SRVLOG=/tmp/bk_web_srv.log
CF="$HOME/.local/bin/cloudflared"

SRV_PID=""; CF_PID=""
cleanup() {
  [ -n "$SRV_PID" ] && kill "$SRV_PID" 2>/dev/null
  [ -n "$CF_PID" ] && kill "$CF_PID" 2>/dev/null
}
trap cleanup EXIT INT TERM

echo ""
echo "  备考刷题 · 网页版 启动中…（建立公网隧道约 10 秒）"
echo ""

# 清理残留
lsof -ti :$PORT 2>/dev/null | xargs kill 2>/dev/null
pkill -f "cloudflared tunnel --url http://localhost:$PORT" 2>/dev/null
sleep 0.5

# 1) 本地服务
cd "$DIR" || exit 1
python3 -m http.server $PORT >"$SRVLOG" 2>&1 &
SRV_PID=$!

# 2) 公网隧道
"$CF" tunnel --url "http://localhost:$PORT" >"$LOG" 2>&1 &
CF_PID=$!

# 3) 提取公网网址
URL=""
for i in $(seq 1 30); do
  URL=$(grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" "$LOG" 2>/dev/null | head -1)
  [ -n "$URL" ] && break
  sleep 1
done

if [ -z "$URL" ]; then
  LAN=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "127.0.0.1")
  echo ""
  echo "  ✗ 公网隧道建立失败（可能断网）。"
  echo "    备用方案：手机与 Mac 连同一 Wi-Fi，打开 http://$LAN:$PORT/"
  echo "    （窗口保持打开，按 Ctrl+C 退出）"
  sleep 3600
  exit 1
fi

# 4) 生成二维码并弹出
QR_PNG="$DIR/备考刷题_扫码打开.png"
python3 "$DIR/build/make_qr.py" "$URL" "$QR_PNG" >/dev/null 2>&1
open "$QR_PNG" 2>/dev/null
printf '%s\n' "$URL" > "$DIR/备考刷题_网页网址.txt"

echo ""
echo "  ┌────────────────────────────────────────────────┐"
echo "  │  ✓ 网页版已上线，二维码窗口已弹出                │"
echo "  │                                                │"
printf "  │  手机打开：%s\n" "$URL"
echo "  │                                                │"
echo "  │  · 手机扫码，或手动输入上面的网址               │"
echo "  │  · 打开后建议「添加到主屏幕」→ 离线可用         │"
echo "  │  · 网址已存到 备考刷题_v1/备考刷题_网页网址.txt │"
echo "  │  · 网址每次启动会变；本窗口别关，关了网页失效   │"
echo "  └────────────────────────────────────────────────┘"
echo ""

# 5) Mac 上自己也打开一份
open "http://localhost:$PORT/" 2>/dev/null

wait
