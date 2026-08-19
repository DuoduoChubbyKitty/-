#!/usr/bin/env python3
"""第一步（用户口述）：保留彩色，对通道操作。
绿通道 ×3；白/亮通道 ×5（红通道拉满提白线）；蓝通道 ×0.1 往死里压；
黄线靠 绿+红 保留。降分辨率1200宽，内存安全。
"""
import cv2
import numpy as np

SRC = "/Users/dupi/Desktop/自动驾驶系统/档案留存/游戏画面_速度测试.png"
OUT = "/Users/dupi/Desktop/自动驾驶系统/pre_step1.png"

img = cv2.imread(SRC)
H, W = img.shape[:2]
tw = 1200
if W > tw:
    img = cv2.resize(img, (tw, int(H * tw / W)))
    H, W = img.shape[:2]

b, g, r = cv2.split(img.astype(np.float32))
# 绿通道 提亮3倍
g = np.clip(g * 3.0, 0, 255)
# 白/亮通道 提亮5倍（红通道拉满，白线=高R高G，蓝已压死）
r = np.clip(r * 5.0, 0, 255)
# 蓝通道 往死里压
b = b * 0.1
out = cv2.merge([b, g, r]).astype(np.uint8)
cv2.imwrite(OUT, out)
print(f"saved {OUT}  shape={out.shape}  ops: 绿×3  白(红)×5  蓝×0.1")
