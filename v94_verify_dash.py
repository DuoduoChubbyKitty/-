"""验证：图上车道线断开，是游戏虚线还是 blob 过滤切断。
做法：取左双黄线所在的一行（真实路面双黄线为连续实线），
分别量 原图 与 预处理图 在该行的"黄/白存在"分布，对比缺口。
"""
import cv2, numpy as np, sys

SRC = "/Users/dupi/Desktop/自动驾驶系统/档案留存/游戏画面_速度测试.png"
BOOST = "/Users/dupi/Desktop/自动驾驶系统/v94_boosted.png"
img = cv2.imread(SRC)
boost = cv2.imread(BOOST)
H, W = img.shape[:2]
bh, bw = boost.shape[:2]
boost_gray = cv2.cvtColor(boost, cv2.COLOR_BGR2GRAY) if boost.ndim == 3 else boost
bh, bw = boost_gray.shape[:2]

def lane_presence(row_bgr):
    """返回该行每个 x 是否判定为'车道(黄或白)'的 0/1 数组（原图用HLS）。"""
    hls = cv2.cvtColor(row_bgr, cv2.COLOR_BGR2HLS)
    yellow = cv2.inRange(hls, (18, 80, 100), (40, 255, 255))
    white = cv2.inRange(hls, (0, 130, 0), (179, 255, 80))
    return ((yellow > 0) | (white > 0)).astype(np.uint8)

# 找双黄线所在的行：底部 0.78H 附近，扫描哪一行左半部黄像素最多
best_y, best_cnt = 0, -1
for y in range(int(H*0.60), int(H*0.92)):
    row = img[y:y+1, :]
    hls = cv2.cvtColor(row, cv2.COLOR_BGR2HLS)
    ymask = cv2.inRange(hls, (18, 80, 100), (40, 255, 255))
    if ymask[:, :W//2].sum() > best_cnt:
        best_cnt = ymask[:, :W//2].sum()
        best_y = y
print(f"[verify] 双黄线最强行 y={best_y} ({best_y/H:.3f}H)  左半黄像素={int(best_cnt)}")

orig_row = img[best_y:best_y+1, :]
# boosted 是灰度单通道且已缩放到 bw×bh，按高度比例映射到对应行
by = int(best_y * bh / H)
boost_row = boost_gray[by:by+1, :]
po = lane_presence(orig_row).ravel()
pb = (boost_row.ravel() > 0).astype(np.uint8)   # 灰度图：>0 即车道像素

def gaps(pres):
    """返回车道段的x区间列表。"""
    n = len(pres)
    segs = []
    in_seg = False
    for x in range(n):
        if pres[x] and not in_seg:
            s = x; in_seg = True
        elif not pres[x] and in_seg:
            segs.append((s, x-1)); in_seg = False
    if in_seg:
        segs.append((s, n-1))
    return segs

so = gaps(po)
sb = gaps(pb)
print(f"\n原图 该行车道段数={len(so)}:")
for (a,b) in so:
    print(f"   x=[{a},{b}]  中心={((a+b)/2/W):.3f}w  宽={b-a}px")
print(f"\n预处理图 该行车道段数={len(sb)}:")
for (a,b) in sb:
    print(f"   x=[{a},{b}]  中心={((a+b)/2/bw):.3f}w  宽={b-a}px")

# 关键判定：左双黄线在原图里应当是连续实线（1段）；若预处理图分裂成多段=被切断
print(f"\n[判定] 原图左黄线段数={len(so)}  预处理图段数={len(sb)}")
if len(sb) > len(so) + 1:
    print("  => 预处理图比原图多出断口，blob 过滤把实线切断了（我的锅）")
else:
    print("  => 预处理图断口数≈原图，断开来自原图本身（游戏虚线/画面结构）")
