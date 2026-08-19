import cv2, numpy as np

SRC = "/Users/dupi/Desktop/自动驾驶系统/档案留存/游戏画面_速度测试.png"
img = cv2.imread(SRC)
H, W = img.shape[:2]
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
V = hsv[:, :, 2].astype(int)
S = hsv[:, :, 1].astype(int)

white_strict = cv2.inRange(hsv, (0, 0, 130), (179, 100, 255))
sky = int(H * 3 / 8)

# 找严格白线 mask 的连通块（轮廓法，避开 connectedComponents 爆内存）
cnts, _ = cv2.findContours(white_strict, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
cands = []
for c in cnts:
    x, y, w, h = cv2.boundingRect(c)
    area = cv2.contourArea(c)
    if h < 0.08 * H:
        continue            # 太矮，不是车道线
    if x + w / 2 < 0.5 * W:
        continue            # 只要右半
    cands.append((x, y, w, h, area))
cands.sort(key=lambda t: t[0])  # 按 x 排序
print(f"右半白线候选块数: {len(cands)}")
for (x, y, w, h, a) in cands:
    y0, y1 = y, y + h
    print(f"  x={x}~{x+w}({x/W:.2f}~{(x+w)/W:.2f}W)  y={y0}~{y1}({y0/H:.2f}~{y1/H:.2f}H)  h={h}px area={int(a)}")

# 取最靠右、最高的那条作为"右白线"，逐行看覆盖
if cands:
    cands.sort(key=lambda t: -(t[3]))
    x, y, w, h, a = cands[0]
    x0, x1 = x, x + w
    y0, y1 = y, y + h
    print(f"\n右白线主体: x={x0}~{x1}  y={y0}~{y1}  总高={y1-y0}px")
    rows_total = y1 - y0
    rows_gap = 0
    for yy in range(y0, y1):
        c = int((white_strict[yy, x0:x1 + 1] > 0).sum())
        if c == 0:
            rows_gap += 1
    print(f"该块 y 跨度内: 完全无白像素的行={rows_gap}/{rows_total} ({100*rows_gap/rows_total:.0f}%)")
    # 上半 vs 下半 覆盖率
    ym = (y0 + y1) // 2
    cov_up = int((white_strict[y0:ym, x0:x1 + 1] > 0).sum())
    cov_dn = int((white_strict[ym:y1, x0:x1 + 1] > 0).sum())
    area_up = (ym - y0) * (x1 - x0)
    area_dn = (y1 - ym) * (x1 - x0)
    print(f"上半覆盖率={100*cov_up/area_up:.1f}%   下半覆盖率={100*cov_dn/area_dn:.1f}%")
    # 上半被滤像素的 S/V
    up_fail_S = S[y0:ym, x0:x1 + 1][(V[y0:ym, x0:x1 + 1] > 120) & (S[y0:ym, x0:x1 + 1] < 120) & (white_strict[y0:ym, x0:x1 + 1] == 0)]
    up_fail_V = V[y0:ym, x0:x1 + 1][(V[y0:ym, x0:x1 + 1] > 120) & (S[y0:ym, x0:x1 + 1] < 120) & (white_strict[y0:ym, x0:x1 + 1] == 0)]
    if up_fail_S.size:
        print(f"上半被滤(疑似白)像素: 平均S={up_fail_S.mean():.1f} 平均V={up_fail_V.mean():.1f}  -> 远半偏色/偏暗")
