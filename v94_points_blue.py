#!/usr/bin/env python3
"""颜色法 v9.4 蓝色点云，叠加在【原始游戏截图】上（非灰度图）。
detect 跑原图全分辨率，点直接落在原图坐标，算法一字未改。"""
import cv2
import numpy as np
import sys
import lane_cv2_v9 as A

SRC = sys.argv[1] if len(sys.argv) > 1 else "/Users/dupi/Desktop/自动驾驶系统/档案留存/游戏画面_速度测试.png"
OUT = "/Users/dupi/Desktop/自动驾驶系统/v94_color_points_blue.png"
R = 4  # 点半径，原图分辨率大，放大点径好分辨

img = cv2.imread(SRC)
if img is None:
    print("MISSING", SRC)
    sys.exit(1)

det = A.detect(img)  # 跑原图
L = det.get('left_pts')
Rr = det.get('right_pts')

vis = img.copy()
for pts in (L, Rr):
    if pts is None or len(pts[0]) == 0:
        continue
    xs, ys = pts
    for x, y in zip(xs.astype(int), ys.astype(int)):
        cv2.circle(vis, (int(x), int(y)), R + 3, (180, 60, 60), -1)  # 淡蓝光晕
        cv2.circle(vis, (int(x), int(y)), R, (255, 0, 0), -1)          # 极亮蓝点

cv2.imwrite(OUT, vis)
print(f"[blue-pts on original] left={len(L[0]) if L is not None else 0} "
      f"right={len(Rr[0]) if Rr is not None else 0} saved {OUT} {vis.shape}")
