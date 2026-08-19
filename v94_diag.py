#!/usr/bin/env python3
"""诊断 v94_pre.py 的 blob 过滤是否误删车道线"""
import cv2
import numpy as np

SRC = "/Users/dupi/Desktop/自动驾驶系统/档案留存/游戏画面_速度测试.png"

def masks():
    img = cv2.imread(SRC)
    H, W = img.shape[:2]
    tw = 1200
    if W > tw:
        img = cv2.resize(img, (tw, int(H * tw / W)))
    H, W = img.shape[:2]
    hls = cv2.cvtColor(img, cv2.COLOR_BGR2HLS)
    yellow = cv2.inRange(hls, (18, 80, 100), (40, 255, 255))
    white = cv2.inRange(hls, (0, 130, 0), (179, 255, 80))
    white = cv2.bitwise_and(white, cv2.bitwise_not(yellow))
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    yellow = cv2.morphologyEx(yellow, cv2.MORPH_CLOSE, k)
    white = cv2.morphologyEx(white, cv2.MORPH_CLOSE, k)
    sky = int(H * 3 / 8)
    yellow[:sky] = 0
    white[:sky] = 0
    return img, yellow, white


def drop_stats(mask, name, MIN_AREA=50, MIN_ELONG=3.0):
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    kept_mask = np.zeros_like(mask)
    before = (mask > 0).sum()
    dropped = []
    for c in cnts:
        area = cv2.contourArea(c)
        x, y, w, h = cv2.boundingRect(c)
        cx, cy = x + w / 2, y + h / 2
        ratio = max(w, h) / max(min(w, h), 1)
        if area >= MIN_AREA or ratio >= MIN_ELONG:
            cv2.drawContours(kept_mask, [c], -1, 255, -1)
        else:
            dropped.append({
                'area': area,
                'bbox': (x, y, w, h),
                'center': (cx / mask.shape[1], cy / mask.shape[0]),
                'ratio': ratio
            })
    after = (kept_mask > 0).sum()
    print(f"\n[{name}] before={before}px  after={after}px  dropped={before-after}px  "
          f"components={len(cnts)}  dropped_components={len(dropped)}")
    if dropped:
        dropped.sort(key=lambda d: d['area'], reverse=True)
        print(f"  最大10个被删连通块 (area / 宽高 / 中心 / 长宽比) — 只该有圆的，不该有细长):")
        for d in dropped[:10]:
            print(f"    area={d['area']:.0f}  bbox={d['bbox']}  "
                  f"center=({d['center'][0]:.3f}w,{d['center'][1]:.3f}h)  "
                  f"ratio={d['ratio']:.1f}")
    return kept_mask


img, y, w = masks()
y2 = drop_stats(y, "YELLOW")
w2 = drop_stats(w, "WHITE")

# 给被删像素标红画出来，看是不是车道线
vis = np.zeros((img.shape[0], img.shape[1], 3), np.uint8)
vis[y > 0] = (255, 255, 255)   # 黄过滤前=白
vis[y2 > 0] = (0, 255, 0)      # 黄过滤后=绿
vis[w > 0] = (255, 255, 255)   # 白过滤前=白
vis[w2 > 0] = (0, 255, 0)      # 白过滤后=绿
cv2.imwrite("/Users/dupi/Desktop/自动驾驶系统/v94_blob_dropped.png", vis)
print("\nsaved v94_blob_dropped.png  (白=过滤前存在  绿=过滤后保留  黑=被blob删除)")
