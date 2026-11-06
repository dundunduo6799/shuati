#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成"扫码打开备考刷题"二维码展示图。用法: make_qr.py <url> <输出png>"""
import sys, os

url, out = sys.argv[1], sys.argv[2]
try:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "qrlib"))
    import qrcode
except ImportError:
    sys.exit("qrcode 模块缺失")

from PIL import Image, ImageDraw, ImageFont

qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=12, border=2)
qr.add_data(url)
qr.make(fit=True)
img = qr.make_image(fill_color="#1e3a8a", back_color="white").convert("RGB")

W = img.width + 120
fH = 170
canvas = Image.new("RGB", (W, img.height + fH), "white")
canvas.paste(img, (60, 50))
d = ImageDraw.Draw(canvas)
try:
    font = ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", 44, index=0)
except Exception:
    font = ImageFont.load_default()
d.text((60, img.height + 75), "手机扫码打开 · 备考刷题", fill="#1e3a8a", font=font)
try:
    small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 26)
except Exception:
    small = font
d.text((60, img.height + 125), url, fill="#555555", font=small)
canvas.save(out)
print("QR:", out)
