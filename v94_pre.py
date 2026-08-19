#!/usr/bin/env python3
"""v9.4 预处理：把同一张图做成「灰度黑底 + 黄白拉满」的隔离图。
复用 v9.4 自己的 HLS 阈值(18-40黄 / 130-255高L低S白)，保证公平。
输出 v94_boosted.png（降分辨率到宽1200，内存安全），并打印底部黄/白峰。
"""
import cv2
import numpy as np
import sys

SRC = "/Users/dupi/Desktop/自动驾驶系统/档案留存/游戏画面_速度测试.png"
OUT = "/Users/dupi/Desktop/自动驾驶系统/v94_boosted.png"
RED = "/Users/dupi/Desktop/自动驾驶系统/v94_redpoints.png"  # 红点图：隔离掩膜以红点呈现，供核对小噪点"

img = cv2.imread(SRC)
H, W = img.shape[:2]

# 降分辨率，内存安全（避免 2940x1912 大 PNG 触发 WorkBuddy 吃内存）
tw = 1200
if W > tw:
    f = tw / W
    img = cv2.resize(img, (tw, int(H * f)))
H, W = img.shape[:2]

# ---- HLS 隔离黄/白（与 v9.4 同阈值，仅用于诊断/天空/小噪点屏蔽）----
hls = cv2.cvtColor(img, cv2.COLOR_BGR2HLS)
yellow = cv2.inRange(hls, (18, 80, 100), (40, 255, 255))
white = cv2.inRange(hls, (0, 130, 0), (179, 255, 80))
white = cv2.bitwise_and(white, cv2.bitwise_not(yellow))

k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
yellow = cv2.morphologyEx(yellow, cv2.MORPH_CLOSE, k)
white = cv2.morphologyEx(white, cv2.MORPH_CLOSE, k)

# ---- 去天空：去掉顶部 SKY_FRAC（车道线只在下方，天空产生假白/假黄）----
SKY_FRAC = 3 / 8                        # 你定的：去掉 3/8 天空（若指 3.5/8≈0.4375 改这一行）
sky_cut = int(H * SKY_FRAC)
yellow[:sky_cut, :] = 0
white[:sky_cut, :] = 0

# ---- 第二步：屏蔽极小连通块（落叶/碎屑等小噪点）----
# 只丢"小+圆"的连通块（落叶/碎屑），"小但细长"的可能是远端车道段，保留。
# 用轮廓面积 + 长宽比：面积>=MIN_AREA 或 长宽比>=MIN_ELONG 都保留。
# 避开 connectedComponentsWithStats，4K 不爆内存。
MIN_AREA = 50
MIN_ELONG = 3.0  # 细长条（车道段）保留


def drop_small(mask):
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = np.zeros_like(mask)
    kept = 0
    for c in cnts:
        area = cv2.contourArea(c)
        x, y, w, h = cv2.boundingRect(c)
        elong = max(w, h) / max(min(w, h), 1)
        if area >= MIN_AREA or elong >= MIN_ELONG:
            cv2.drawContours(out, [c], -1, 255, -1)
            kept += 1
    return out, kept


yellow, ny = drop_small(yellow)
white, nw = drop_small(white)
print(f"[filter] 黄连通块保留={ny}  白连通块保留={nw}  "
      f"(丢弃<{MIN_AREA}px 且长宽比<{MIN_ELONG}的圆小噪点)")

# ---- 灰度图 + 黄/白拉满 + 其余压死 ----
# 你要的：转灰度 → 黄色车道拉满 → 白色车道拉满 → 其他压死(黑)。
# 单通道灰度：车道像素=255，其余=0（压死）。天空已在 masks 清零、blob 已屏蔽。
gray_out = np.zeros((H, W), np.uint8)   # 黑底 = 其余压死
gray_out[yellow > 0] = 255               # 黄色车道拉满
gray_out[white > 0] = 255               # 白色车道拉满
boosted = gray_out                       # 单通道灰度图

# ---- 红点图：隔离掩膜以红点呈现（核对小噪点是否清掉）----
redpts = np.zeros((H, W, 3), np.uint8)
redpts[yellow > 0] = (0, 0, 255)
redpts[white > 0] = (0, 0, 255)
cv2.imwrite(RED, redpts)

# ---- 打印底部峰，验证内白线在不在 ----
yb, yh = int(H * 0.82), int(H * 0.92)


def peaks(mask, name):
    band = mask[yb:yh, :]
    hist = np.sum(band, axis=0).astype(np.float32)
    if hist.max() == 0:
        print(f"{name} none"); return
    hs = cv2.GaussianBlur(hist.reshape(1, -1), (1, 31), 0).ravel()
    mv = hs.max()
    mh = mv * 0.10 if mv > 50 else 20
    pk = [i for i in range(1, W - 1)
          if hs[i] > hs[i - 1] and hs[i] > hs[i + 1] and hs[i] >= mh]
    print(f"{name} peaks={pk}  frac={[round(p / W, 3) for p in pk]}")


peaks(yellow, "YELLOW")
peaks(white, "WHITE")
cv2.imwrite(OUT, boosted)
print(f"saved {OUT} {boosted.shape}")
