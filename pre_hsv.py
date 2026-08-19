import cv2, numpy as np

SRC = "/Users/dupi/Desktop/自动驾驶系统/档案留存/游戏画面_速度测试.png"
OUT = "/Users/dupi/Desktop/自动驾驶系统/pre_hsv.png"

img = cv2.imread(SRC)
H, W = img.shape[:2]

# ---- HSV 颜色空间 mask 筛选（精确留黄/白，其余压黑）----
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

# 黄色：色相偏黄 + 一定饱和 + 不靠亮度(抗阴影用 S/H 判定)
yellow = cv2.inRange(hsv, (15, 60, 30), (35, 255, 255))
# 白色：低饱和 + 高亮(白线)
white = cv2.inRange(hsv, (0, 0, 160), (179, 50, 255))
# 黄白合并
mask = cv2.bitwise_or(yellow, white)

# 形态学闭运算，补小缝
k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)

# 掩膜内保留原始彩色，掩膜外压黑
out = np.zeros_like(img)
out[mask > 0] = img[mask > 0]

# 去天空 3/8
SKY_FRAC = 3 / 8
sky_cut = int(H * SKY_FRAC)
out[:sky_cut, :] = 0
mask[:sky_cut, :] = 0

cv2.imwrite(OUT, out)
print(f"saved {OUT}  shape={out.shape}")
print(f"[HSV mask] 黄像素={int((yellow>0).sum())}  白像素={int((white>0).sum())}  "
      f"合并={int((mask>0).sum())}px ({100*(mask>0).sum()/(H*W):.2f}%)")
