import cv2, numpy as np

SRC = '/Users/dupi/Desktop/自动驾驶系统/档案留存/游戏画面_速度测试.png'
OUT = '/Users/dupi/Desktop/自动驾驶系统/pre_gray.png'

img = cv2.imread(SRC)
# 1) 绿通道提到扎眼
g = img[:, :, 1].astype(np.float32) * 5.0
img[:, :, 1] = np.clip(g, 0, 255).astype(np.uint8)
# 2) 蓝通道往死里压
b = img[:, :, 0].astype(np.float32) * 0.1
img[:, :, 0] = np.clip(b, 0, 255).astype(np.uint8)
# 3) 红通道不动（不用红色代替白色）
# 4) 转标准灰度图
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
# 5) 去天空：顶部 3.6/8 直接裁掉（车道线只在下方，天空产生假白/假黄）
SKY_FRAC = 3.0 / 8.0
sky_cut = int(gray.shape[0] * SKY_FRAC)
gray[:sky_cut, :] = 0
cv2.imwrite(OUT, gray)
print('saved', OUT, gray.shape, 'sky_cut=%d (%.3f H)' % (sky_cut, SKY_FRAC))
