import cv2, numpy as np

SRC = "/Users/dupi/Desktop/自动驾驶系统/档案留存/游戏画面_速度测试.png"
img = cv2.imread(SRC)
H, W = img.shape[:2]
print(f"图像尺寸: {W}x{H}")
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
V = hsv[:, :, 2].astype(int)
S = hsv[:, :, 1].astype(int)
Hh = hsv[:, :, 0].astype(int)

# 颜色 mask（与 pre_combo2 一致）
yellow = cv2.inRange(hsv, (15, 60, 30), (35, 255, 255))
white = cv2.inRange(hsv, (0, 0, 130), (179, 100, 255))
lane_mask = cv2.bitwise_or(yellow, white)

sky = int(H * 3.2 / 8)
ground = slice(sky, H)

# 地面区域里，原始像素的色相分布（落叶多为黄/橙/棕）
gH = Hh[ground].ravel()
gS = S[ground].ravel()
gV = V[ground].ravel()
# 落叶（黄/橙/棕）通常 H 在 5~35、S 中高、V 中低
leafish = (gH >= 5) & (gH <= 35) & (gS >= 40) & (gV >= 20) & (gV <= 200)
print(f"地面像素总数={gH.size}  落叶色(黄橙棕)像素={int(leafish.sum())} ({100*leafish.sum()/gH.size:.1f}%)")

# 落叶色像素里，有多少通过了车道 mask（会被当成车道候选）
leaf_pass = leafish & (lane_mask[ground].ravel() > 0)
print(f"落叶色像素中通过车道mask的={int(leaf_pass.sum())} ({100*leaf_pass.sum()/max(1,leafish.sum()):.1f}% of 落叶色)")
print(f"地面里车道mask总亮像素={int((lane_mask[ground]>0).sum())} ({100*(lane_mask[ground]>0).sum()/gH.size:.1f}%)")

# 车道mask在地面里的连通块面积分布（看落叶是铺成大片还是小斑点）
cnts, _ = cv2.findContours(lane_mask[ground], cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
areas = sorted([cv2.contourArea(c) for c in cnts], reverse=True)
print(f"地面车道mask连通块数={len(areas)}")
print(f"  最大块面积={areas[0]:.0f}px  前5大={[round(a) for a in areas[:5]]}")
big = sum(1 for a in areas if a >= 200)
small = sum(1 for a in areas if a < 50)
print(f"  大面积块(>=200px, 像落叶毯/大块)={big}  小斑点(<50px)={small}")
