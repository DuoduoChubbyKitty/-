"""正确验证：车道线断开是不是 blob 过滤切断的。
方法：复刻 v94_pre.py 的隔离流水线（HLS黄白+形态学闭+去天空），
但不做 drop_small，得到'过滤前'掩膜；和最终 boosted 图(=过滤后)对比。
在同一行(双黄线最强处)看：过滤前 vs 过滤后 车道像素是否多出断口。
"""
import cv2, numpy as np

SRC = "/Users/dupi/Desktop/自动驾驶系统/档案留存/游戏画面_速度测试.png"
BOOST = "/Users/dupi/Desktop/自动驾驶系统/v94_boosted.png"
img = cv2.imread(SRC)
boost = cv2.imread(BOOST)
boost_gray = cv2.cvtColor(boost, cv2.COLOR_BGR2GRAY) if boost.ndim == 3 else boost
H, W = img.shape[:2]
bh, bw = boost_gray.shape[:2]

# ---- 复刻预处理隔离(不过滤小连通块) ----
PROC_W = 1200
scale = PROC_W / W
small = cv2.resize(img, (PROC_W, int(H * scale)))
Hr, Wr = small.shape[:2]
hls = cv2.cvtColor(small, cv2.COLOR_BGR2HLS)
yellow = cv2.inRange(hls, (18, 80, 100), (40, 255, 255))
white = cv2.inRange(hls, (0, 130, 0), (179, 255, 80))
white = cv2.bitwise_and(white, cv2.bitwise_not(yellow))
k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
yellow = cv2.morphologyEx(yellow, cv2.MORPH_CLOSE, k)
white = cv2.morphologyEx(white, cv2.MORPH_CLOSE, k)
SKY_FRAC = 3/8
sky_cut = int(Hr * SKY_FRAC)
yellow[:sky_cut, :] = 0
white[:sky_cut, :] = 0
pre = ((yellow > 0) | (white > 0)).astype(np.uint8)   # 过滤前

post = (boost_gray > 0).astype(np.uint8)              # 过滤后(最终 boosted)

# 找双黄线最强行（在 pre 上，底部 0.60~0.92H）
best_y, best_cnt = 0, -1
for y in range(int(Hr*0.60), int(Hr*0.92)):
    c = pre[y, :Wr//2].sum()
    if c > best_cnt:
        best_cnt = c; best_y = y

def gaps(pres):
    n = len(pres); segs = []; in_seg = False; s = 0
    for x in range(n):
        if pres[x] and not in_seg: s = x; in_seg = True
        elif not pres[x] and in_seg: segs.append((s, x-1)); in_seg = False
    if in_seg: segs.append((s, n-1))
    return segs

pre_row = pre[best_y]
post_row = post[best_y]
gp = gaps(pre_row); gb = gaps(post_row)
print(f"[verify] 双黄线行 y={best_y}/{bh}  过滤前段数={len(gp)}  过滤后段数={len(gb)}")

# 只比较左黄线带(0.18~0.32w)里，过滤后比过滤前多出的断口
def in_band(seg, lo, hi): return lo <= (seg[0]+seg[1])/2/Wr <= hi
LO, HI = 0.18, 0.32
pre_band = [s for s in gp if in_band(s, LO, HI)]
post_band = [s for s in gb if in_band(s, LO, HI)]
print(f"\n左黄线带(0.18~0.32w):")
print(f"  过滤前段: {[(round((a+b)/2/Wr,3), b-a) for a,b in pre_band]}")
print(f"  过滤后段: {[(round((a+b)/2/Wr,3), b-a) for a,b in post_band]}")

# 过滤前在带内应是1段实线；过滤后被切成多段=我的过滤切断
if len(post_band) > len(pre_band):
    print(f"\n[结论] 过滤后段数({len(post_band)}) > 过滤前({len(pre_band)}) "
          f"=> blob 过滤在该行把实线切出了 {len(post_band)-len(pre_band)} 个新断口，是我的锅。")
else:
    print(f"\n[结论] 过滤后段数({len(post_band)}) <= 过滤前({len(pre_band)}) "
          f"=> 该行断开不是 blob 过滤新造成的（过滤前就已断开=源图/游戏本身）。")
