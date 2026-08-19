#!/usr/bin/env python3
# 实验：验证"颜色隔离预处理是否导致 A 选错右基"
# 在同一张图上用三种白线识别方式算底部白峰，并套用相同的 min_sep 约束看右基选中谁。
import cv2
import numpy as np

IMG = "/Users/dupi/Desktop/自动驾驶系统/档案留存/游戏画面_速度测试.png"
img = cv2.imread(IMG)
H, W = img.shape[:2]
hls = cv2.cvtColor(img, cv2.COLOR_BGR2HLS)
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

def white_peaks_from_mask(white):
    band_y_low, band_y_high = int(H*0.82), int(H*0.92)
    band = white[band_y_low:band_y_high, :]
    hist = np.sum(band, axis=0).astype(np.float32)
    if hist.max() == 0:
        return []
    hist_s = cv2.GaussianBlur(hist.reshape(1, -1), (1, 31), 0).ravel()
    min_h = max(hist_s.max() * 0.10, 20)
    peaks = [i for i in range(1, W-1)
             if hist_s[i] > hist_s[i-1] and hist_s[i] > hist_s[i+1] and hist_s[i] >= min_h]
    return peaks

# 三种白线识别
m_hls = cv2.inRange(hls, np.array([0,130,0]), np.array([179,255,80]))           # 当前：HLS 高L低S
m_gray200 = (gray > 200).astype(np.uint8) * 255                                  # 纯灰度>200
m_gray180 = (gray > 180).astype(np.uint8) * 255                                  # 纯灰度>180

left_base = 938  # 当前 A 选定的左基（黄峰 0.319W）
center = W / 2

print(f"image {W}x{H}  left_base={left_base}({left_base/W:.3f}w)  center={center:.0f}\n")
for name, m in [("HLS隔离(当前)", m_hls), ("灰度>200", m_gray200), ("灰度>180", m_gray180)]:
    peaks = white_peaks_from_mask(m)
    print(f"[{name}] 白峰={peaks} ({[round(p/W,3) for p in peaks]}w)")

# 套用两种 min_sep 约束看右基 picks
print("\n--- 右基选择（left_base=938）---")
for name, m in [("HLS隔离(当前)", m_hls), ("灰度>200", m_gray200), ("灰度>180", m_gray180)]:
    peaks = white_peaks_from_mask(m)
    for minf in (0.35, 0.20):
        min_sep, max_sep = int(W*minf), int(W*0.75)
        cands = [p for p in peaks if p > left_base and min_sep <= (p-left_base) <= max_sep]
        pick = min(cands, key=lambda p: p-left_base) if cands else "NONE(fallback->最右白峰)"
        print(f"  {name:12s} min_sep={minf}W -> 右基={pick}")
