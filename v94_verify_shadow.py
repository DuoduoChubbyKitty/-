"""验证用户判断：阴影下的车道线(仍是绿/黄)是否被 HLS 亮度阈值删除。
做法：在左黄线带里，找'绿通道提亮后仍高、但 HLS 隔离判定为0(被删)'的像素。
"""
import cv2, numpy as np

SRC = "/Users/dupi/Desktop/自动驾驶系统/档案留存/游戏画面_速度测试.png"
img = cv2.imread(SRC)
H, W = img.shape[:2]
PROC_W = 1200
small = cv2.resize(img, (PROC_W, int(H * PROC_W / W)))
Hr, Wr = small.shape[:2]
hls = cv2.cvtColor(small, cv2.COLOR_BGR2HLS)
green = small[:, :, 1].astype(np.float32)
GREEN_GAIN = 2.6
green_boost = np.clip(green * GREEN_GAIN, 0, 255).astype(np.uint8)

# 当前 HLS 隔离(=v94_pre 里的逻辑)
yellow = cv2.inRange(hls, (18, 80, 100), (40, 255, 255))
white = cv2.inRange(hls, (0, 130, 0), (179, 255, 80))
white = cv2.bitwise_and(white, cv2.bitwise_not(yellow))
k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
yellow = cv2.morphologyEx(yellow, cv2.MORPH_CLOSE, k)
white = cv2.morphologyEx(white, cv2.MORPH_CLOSE, k)
yellow[:int(Hr*3/8), :] = 0
white[:int(Hr*3/8), :] = 0
cur = ((yellow > 0) | (white > 0)).astype(np.uint8)

# 左黄线带 0.15~0.33w，且只统计路面区(去掉天空)
sky_cut = int(Hr*3/8)
LO, HI = int(Wr*0.15), int(Wr*0.33)
band_cur = cur[sky_cut:, LO:HI]
band_g = green_boost[sky_cut:, LO:HI]

# 被删的'阴影线像素'：绿提亮后>=90 但 cur==0
deleted_shadow = (band_g >= 90) & (band_cur == 0)
print(f"[verify 仅路面区] 左黄线带内：绿提亮后高(>=90)却被 HLS 隔离删掉的像素数 = {int(deleted_shadow.sum())}")
print(f"         该带总车道像素(绿>=90) = {int((band_g>=90).sum())}  "
      f"被删占比 = {100*deleted_shadow.sum()/max((band_g>=90).sum(),1):.1f}%")

# 找一个具体行示范：路面区里删掉最多阴影像素的那行
ys, xs = np.where(deleted_shadow)
if len(ys):
    from collections import Counter
    rowcnt = Counter(ys.tolist())
    ry = max(rowcnt, key=rowcnt.get)        # 这是相对 sky_cut 的行号
    absy = ry + sky_cut
    print(f"\n[示例行 绝对y={absy}] 该行被删的阴影线像素数={rowcnt[ry]}")
    xsr = np.where(deleted_shadow[ry])[0]
    print(f"  被删像素的相对x(占带): ", [round((LO+x)/Wr, 3) for x in xsr[:20]])
    print(f"  这些点的绿提亮值示例: ", [int(band_g[ry, x]) for x in xsr[:20]])
    print(f"  => 这些点绿通道仍有 {int(band_g[ry, xsr].mean())} 左右(线是绿的)，"
          f"却因 HLS 亮度<130 被判非车道而删除。")
