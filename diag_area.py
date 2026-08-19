import cv2, numpy as np, os

GRAY = "/Users/dupi/Desktop/自动驾驶系统/diag_steps/step4_gray.png"
OUT_DIR = "/Users/dupi/Desktop/自动驾驶系统/diag_area"
os.makedirs(OUT_DIR, exist_ok=True)

g = cv2.imread(GRAY, 0)
_, b = cv2.threshold(g, 10, 255, cv2.THRESH_BINARY)
cnts, _ = cv2.findContours(b, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

for thr in [30, 50, 100, 200, 500]:
    mask = np.zeros_like(g)
    kept = 0
    for c in cnts:
        if cv2.contourArea(c) >= thr:
            cv2.drawContours(mask, [c], -1, 255, -1)
            kept += 1
    res = cv2.bitwise_and(g, mask)
    cv2.imwrite(f"{OUT_DIR}/area_thr{thr}.png", res)
    print(f"thr={thr:3d}  kept={kept}")
