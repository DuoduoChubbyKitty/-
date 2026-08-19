import cv2, numpy as np

SRC = "/Users/dupi/Desktop/自动驾驶系统/档案留存/游戏画面_速度测试.png"
OUT = "/Users/dupi/Desktop/自动驾驶系统/pre_color2.png"

img = cv2.imread(SRC)
PROC_W = 1200
scale = PROC_W / img.shape[1]
small = cv2.resize(img, (PROC_W, int(img.shape[0] * scale)))
Hr, Wr = small.shape[:2]

GREEN = 1.0
RED = 1.0
BLUE = 1.0

f = small.astype(np.float32)
f[:, :, 1] = np.clip(f[:, :, 1] * GREEN, 0, 255)
f[:, :, 2] = np.clip(f[:, :, 2] * RED, 0, 255)
f[:, :, 0] = np.clip(f[:, :, 0] * BLUE, 0, 255)
boosted = f.astype(np.uint8)

SKY_FRAC = 3.0 / 8.0
sky_cut = int(Hr * SKY_FRAC)
boosted[:sky_cut, :] = 0

cv2.imwrite(OUT, boosted)
print(f"saved {OUT} (彩色)  G={GREEN} R={RED} B={BLUE} sky={SKY_FRAC}")
