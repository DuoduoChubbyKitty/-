import cv2, numpy as np

SRC = '/Users/dupi/Desktop/自动驾驶系统/档案留存/游戏画面_速度测试.png'
OUT = '/Users/dupi/Desktop/自动驾驶系统/pre_gray.png'

img = cv2.imread(SRC)
# 1) 绿通道提到扎眼（绿线 + 白线都含绿，靠这一下提亮）
g = img[:, :, 1].astype(np.float32) * 5.0
img[:, :, 1] = np.clip(g, 0, 255).astype(np.uint8)
# 2) 蓝通道往死里压（天空/蓝车基本看不见）
b = img[:, :, 0].astype(np.float32) * 0.1
img[:, :, 0] = np.clip(b, 0, 255).astype(np.uint8)
# 3) 红通道不动（绝不用红色代替白色，否则白线丢）
# 4) 转标准灰度图（单通道黑白）
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
cv2.imwrite(OUT, gray)
print('saved', OUT, gray.shape)
