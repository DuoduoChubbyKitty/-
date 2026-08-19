import cv2, numpy as np

SRC = '/Users/dupi/Desktop/自动驾驶系统/档案留存/游戏画面_速度测试.png'
OUT = '/Users/dupi/Desktop/自动驾驶系统/pre_try3.png'

img = cv2.imread(SRC)
# 绿通道 ×5
img[:, :, 1] = np.clip(img[:, :, 1].astype(np.float32) * 5.0, 0, 255).astype(np.uint8)
# 红通道 ×3
img[:, :, 2] = np.clip(img[:, :, 2].astype(np.float32) * 3.0, 0, 255).astype(np.uint8)
# 蓝通道 ×0.1（压死）
img[:, :, 0] = np.clip(img[:, :, 0].astype(np.float32) * 0.1, 0, 255).astype(np.uint8)
# 转标准灰度
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
# 去天空 3/8
SKY = 3.0 / 8.0
gray[:int(gray.shape[0] * SKY), :] = 0
cv2.imwrite(OUT, gray)
print('saved', OUT, gray.shape)
