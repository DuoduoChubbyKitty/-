import cv2, numpy as np

SRC = '/Users/dupi/Desktop/自动驾驶系统/档案留存/游戏画面_速度测试.png'
OUT = '/Users/dupi/Desktop/自动驾驶系统/pre_gray.png'

img = cv2.imread(SRC)
# 1) 先把绿通道提高 5 倍（把绿色的线提亮）
g = img[:, :, 1].astype(np.float32) * 5.0
img[:, :, 1] = np.clip(g, 0, 255).astype(np.uint8)
# 2) 再转成标准灰度图（黑白单通道）
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
cv2.imwrite(OUT, gray)
print('saved', OUT, gray.shape)
