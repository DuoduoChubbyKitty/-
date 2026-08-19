import cv2, numpy as np

SRC = "/Users/dupi/Desktop/自动驾驶系统/档案留存/游戏画面_速度测试.png"
OUT = "/Users/dupi/Desktop/自动驾驶系统/pre_color5.png"

img = cv2.imread(SRC)
H, W = img.shape[:2]

# 通道级压制（彩色画面，不转灰度）
boosted = img.astype(np.float32)
boosted[:, :, 0] = np.clip(boosted[:, :, 0] * 0.01, 0, 255)   # 蓝 ×0.01（往死里压）
boosted[:, :, 1] = np.clip(boosted[:, :, 1] * 5.0, 0, 255)    # 绿 ×5
boosted[:, :, 2] = np.clip(boosted[:, :, 2] * 5.0, 0, 255)    # 红 ×5
boosted = boosted.astype(np.uint8)

# 去天空 3/8
SKY_FRAC = 3 / 8
sky_cut = int(H * SKY_FRAC)
boosted[:sky_cut, :] = 0

cv2.imwrite(OUT, boosted)
print(f"saved {OUT}  shape={boosted.shape}  绿×5 红×5 蓝×0.01 去天空3/8")
