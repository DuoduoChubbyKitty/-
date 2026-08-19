#!/usr/bin/env python3
"""点云可视化调试 v2：黑白灰度图当底 + 蓝点=OpenCV sliding window 真实采到的点
（即喂给拟合的左右点云）。再叠加细拟合线(黄左/红右)便于对照点vs线。"""
import sys
import cv2
import numpy as np
import lane_cv2_v9 as L

src = sys.argv[1] if len(sys.argv) > 1 else str(L.SRC)
img = cv2.imread(src)
if img is None:
    print(f"FAIL read {src}", file=sys.stderr); sys.exit(1)

gray = L.preprocess(img)
dbg = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)   # 黑白底

r = L.detect(img)
if r.get('left_pts') is None:
    print("MISSING pts"); sys.exit(0)
lx, ly = r['left_pts']
rx, ry = r['right_pts']

# 蓝点：真实采到的点（喂给拟合的左右点云）
for x, y in zip(lx.astype(int), ly.astype(int)):
    if 0 <= y < dbg.shape[0] and 0 <= x < dbg.shape[1]:
        dbg[y, x] = (255, 0, 0)
for x, y in zip(rx.astype(int), ry.astype(int)):
    if 0 <= y < dbg.shape[0] and 0 <= x < dbg.shape[1]:
        dbg[y, x] = (255, 0, 0)

# 叠加平滑拟合曲线（黄左/红右），便于对照点vs线
left_fit = L.fit_smooth(lx, ly, r['roi_top'], r['H'], deg=3)
right_fit = L.fit_smooth(rx, ry, r['roi_top'], r['H'], deg=3)
L.draw_smooth(dbg, left_fit, r['roi_top'], r['H'], (0, 255, 255), thickness=3)
L.draw_smooth(dbg, right_fit, r['roi_top'], r['H'], (0, 0, 255), thickness=3)

cv2.imwrite('pointcloud_debug.png', dbg)
print(f"saved pointcloud_debug.png  left_pts={len(lx)} right_pts={len(rx)}")
print("底=预处理黑白灰度图  蓝点=OpenCV真实采到的点(喂拟合)  黄线/红线=单条平滑曲线")
