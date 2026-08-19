import cv2, numpy as np

SRC = "/Users/dupi/Desktop/自动驾驶系统/档案留存/游戏画面_速度测试.png"
OUT = "/Users/dupi/Desktop/自动驾驶系统/pre_combo.png"

img = cv2.imread(SRC)
H, W = img.shape[:2]

# ---- 1) HSV mask 筛选（精确留黄/白，其余压黑）----
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
yellow = cv2.inRange(hsv, (15, 60, 30), (35, 255, 255))
white = cv2.inRange(hsv, (0, 0, 160), (179, 50, 255))
mask = cv2.bitwise_or(yellow, white)
k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)

out = np.zeros_like(img)
out[mask > 0] = img[mask > 0]          # 只留黄/白区域的原始彩色，背景黑

# ---- 2) 通道加权 + 亮度 ----
# 绿 ×5，红 ×0.1，蓝 ×0.1
out = out.astype(np.float32)
out[:, :, 0] = out[:, :, 0] * 0.1   # 蓝
out[:, :, 1] = out[:, :, 1] * 5.0   # 绿
out[:, :, 2] = out[:, :, 2] * 0.1   # 红
# 亮度 ×5（整体再提亮）
out = out * 5.0
out = np.clip(out, 0, 255).astype(np.uint8)

# ---- 3) 去天空 3/8 ----
SKY_FRAC = 3 / 8
sky_cut = int(H * SKY_FRAC)
out[:sky_cut, :] = 0

cv2.imwrite(OUT, out)
print(f"saved {OUT}  shape={out.shape}  HSV_mask + 绿×5 红×0.1 蓝×0.1 亮度×5 去天空3/8")
