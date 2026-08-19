import cv2, numpy as np, os

SRC = "/Users/dupi/Desktop/自动驾驶系统/档案留存/游戏画面_速度测试.png"
OUT_DIR = "/Users/dupi/Desktop/自动驾驶系统/diag_steps"
os.makedirs(OUT_DIR, exist_ok=True)

img = cv2.imread(SRC)
H, W = img.shape[:2]

# 1) HSV mask
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
yellow = cv2.inRange(hsv, (15, 60, 30), (35, 255, 255))
white = cv2.inRange(hsv, (0, 0, 130), (179, 100, 255))
mask = cv2.bitwise_or(yellow, white)
k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)
cv2.imwrite(f"{OUT_DIR}/step1_hsv_mask.png", mask)

# 2) color weighted
out = np.zeros_like(img)
out[mask > 0] = img[mask > 0]
out = out.astype(np.float32)
out[:, :, 0] *= 1.0
out[:, :, 1] *= 5.0
out[:, :, 2] *= 1.0
out = out * 2.0
out = np.clip(out, 0, 255).astype(np.uint8)
cv2.imwrite(f"{OUT_DIR}/step2_color.png", out)

# 3) sky cut
out[:int(H * 3.2 / 8), :] = 0
cv2.imwrite(f"{OUT_DIR}/step3_sky.png", out)

# 4) gray
gray = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
cv2.imwrite(f"{OUT_DIR}/step4_gray.png", gray)

# 5) blob filter
_, binar = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY)
cnts, _ = cv2.findContours(binar, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
mask_keep = np.zeros_like(gray)
for c in cnts:
    x, y, w, h = cv2.boundingRect(c)
    aspect = max(w, h) / max(1, min(w, h))
    if aspect >= 3.0:
        cv2.drawContours(mask_keep, [c], -1, 255, -1)
final = cv2.bitwise_and(gray, mask_keep)
cv2.imwrite(f"{OUT_DIR}/step5_blob.png", final)

print(f"saved {OUT_DIR}/step1..5")
print(f"image size: {W}×{H}")
