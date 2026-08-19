import cv2, numpy as np

SRC = "/Users/dupi/Desktop/自动驾驶系统/档案留存/游戏画面_速度测试.png"
OUT = "/Users/dupi/Desktop/自动驾驶系统/pre_combo2.png"

img = cv2.imread(SRC)
H, W = img.shape[:2]

# 1) HSV mask 筛选（留黄/白，其余压黑）
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
yellow = cv2.inRange(hsv, (15, 60, 30), (35, 255, 255))
white = cv2.inRange(hsv, (0, 0, 130), (179, 100, 255))
mask = cv2.bitwise_or(yellow, white)
k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)
out = np.zeros_like(img)
out[mask > 0] = img[mask > 0]

# 2) 通道加权 + 亮度：绿×5，红×1，蓝×1，亮度×2
out = out.astype(np.float32)
out[:, :, 0] = out[:, :, 0] * 1.0   # 蓝 ×1
out[:, :, 1] = out[:, :, 1] * 5.0   # 绿 ×5
out[:, :, 2] = out[:, :, 2] * 1.0   # 红 ×1
out = out * 2.0                     # 亮度 ×2
out = np.clip(out, 0, 255).astype(np.uint8)

# 3) 去天空 3.2/8
SKY_FRAC = 3.2 / 8
out[:int(H * SKY_FRAC), :] = 0

# 4) 转灰度图
gray = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)

# 5) 屏蔽落叶：删除面积过小的零散小块（落叶/碎屑），保留车道线等大结构
#    用 findContours（非 connectedComponentsWithStats，避免 4K 爆内存）
_, binar = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY)
cnts, _ = cv2.findContours(binar, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
mask_keep = np.zeros_like(gray)
MIN_AREA = 500  # 可调：越大删得越狠
for c in cnts:
    if cv2.contourArea(c) >= MIN_AREA:
        cv2.drawContours(mask_keep, [c], -1, 255, -1)
gray = cv2.bitwise_and(gray, mask_keep)

cv2.imwrite(OUT, gray)
print(f"saved {OUT}  HSV_mask+绿×5 红×1 蓝×1 亮度×2 去天空3.2/8 转灰度 落叶过滤(面积≥{MIN_AREA})")
