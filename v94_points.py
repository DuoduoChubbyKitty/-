#!/usr/bin/env python3
"""颜色法 v9.4 纯点云（不连线）：把滑窗检测到的原始点画出来。
左线=红点，右线=黄点，无任何拟合线。"""
import cv2
import numpy as np
import sys
import lane_cv2_v9 as A

SRC = sys.argv[1] if len(sys.argv) > 1 else "/Users/dupi/Desktop/自动驾驶系统/v94_boosted.png"
OUT = "/Users/dupi/Desktop/自动驾驶系统/v94_color_points.png"

img = cv2.imread(SRC)
if img is None:
    print("MISSING", SRC)
    sys.exit(1)

det = A.detect(img)
L = det.get('left_pts')
R = det.get('right_pts')

vis = img.copy()
if L is not None and len(L[0]) > 0:
    lx, ly = L
    for x, y in zip(lx.astype(int), ly.astype(int)):
        cv2.circle(vis, (int(x), int(y)), 1, (0, 0, 255), -1)  # 红=左线
if R is not None and len(R[0]) > 0:
    rx, ry = R
    for x, y in zip(rx.astype(int), ry.astype(int)):
        cv2.circle(vis, (int(x), int(y)), 1, (0, 255, 255), -1)  # 黄=右线

cv2.imwrite(OUT, vis)
print(f"[color-pts] left_pts={len(L[0]) if L is not None else 0} "
      f"right_pts={len(R[0]) if R is not None else 0}  saved {OUT} {vis.shape}")
