#!/usr/bin/env python3
"""手动在 000760.jpg 上折线标注车道线（左黄/右白），作为"矩阵法"参考。"""
import cv2
import numpy as np

src = "/Users/dupi/Desktop/000760.jpg"
out = "/Users/dupi/Desktop/manual_lane_000760.png"
img = cv2.imread(src)
if img is None:
    print("FAIL read", src); exit(1)
H, W = img.shape[:2]

# 手工估计的顶点 (x, y) —— 224x224 图上左黄线/右白线的内沿
left_pts = np.array([[50, H-20], [45, H-60], [55, H-100], [80, H-140], [120, H-170]], np.int32)
right_pts = np.array([[170, H-20], [175, H-60], [170, H-100], [150, H-140], [130, H-170]], np.int32)

vis = img.copy()
cv2.polylines(vis, [left_pts], False, (0, 255, 255), 2)  # 黄 = 左内黄线
cv2.polylines(vis, [right_pts], False, (0, 0, 255), 2)    # 红 = 右内白线

# 标出顶点（矩阵点）
for p in left_pts:
    cv2.circle(vis, tuple(p), 3, (0, 255, 255), -1)
for p in right_pts:
    cv2.circle(vis, tuple(p), 3, (0, 0, 255), -1)

cv2.imwrite(out, vis)
print(f"saved {out}  左黄={len(left_pts)}点 右红={len(right_pts)}点")
