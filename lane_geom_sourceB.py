#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
几何法 Source B (降分辨率 + 颜色隔离 + 车道宽配对 + 防闪)
只出原始点云 -> RDP 折线 -> trim_collinear 删外凸中间点

detect(small) 返回左/右车道逐行 x 字典 (行号->x, small 分辨率像素)，
供 fuse.py 做行级融合。main() 行为与原版一致（点云 + 干净折线 png）。
"""
import sys, time, resource
import numpy as np
import cv2

IMG = "档案留存/游戏画面_速度测试.png"   # 默认已知好场景；运行时 argv[1] 可覆盖为其他截图
PROC_W = 480
CROP_BOTTOM = 1.0 / 8.0   # 裁掉最底部 1/8（非游戏 HUD/状态条），用户要求
PREFIX = "lane_geom_B"    # 输出文件前缀；运行时 argv[2] 可覆盖
SKY_CUT = 0.375
ROI_TOP = 0.45
WIN0 = 0.06
MAXDX = 0.03
OUT_PTS = PREFIX + "_pts.png"
OUT_ISO = PREFIX + "_iso.png"
OUT_CURVE = PREFIX + "_curve.png"

def log(*a):
    print("[geomB]", *a, file=sys.stderr, flush=True)

def color_masks(small):
    hls = cv2.cvtColor(small, cv2.COLOR_BGR2HLS)
    Hc, Lc, Sc = hls[:, :, 0].astype(np.int16), hls[:, :, 1].astype(np.int16), hls[:, :, 2].astype(np.int16)
    ym = ((Hc >= 18) & (Hc <= 40) & (Lc >= 110) & (Lc < 255) & (Sc >= 110) & (Sc < 255)).astype(np.uint8)
    wm = ((Lc >= 150) & (Lc < 255) & (Sc < 70)).astype(np.uint8)
    del hls, Hc, Lc, Sc
    k = np.ones((3, 3), np.uint8)
    ym = cv2.morphologyEx(ym, cv2.MORPH_OPEN, k)
    wm = cv2.morphologyEx(wm, cv2.MORPH_OPEN, k)
    ym[:int(SKY_CUT * small.shape[0]), :] = 0
    wm[:int(SKY_CUT * small.shape[0]), :] = 0
    return ym, wm

def anchor_bottom(maskc, y0f, y1f):
    """从底(y1f)向上扫, 返回最底行有像素的质心 x 与行号"""
    y1 = int(y1f * maskc.shape[0]) - 1
    y0 = int(y0f * maskc.shape[0])
    for y in range(y1, y0 - 1, -1):
        xs = np.nonzero(maskc[y])[0]
        if xs.size:
            return int(xs.mean()), y
    return None, None

def track_dir(maskc, x0, y0, y_end, step, pred_slope=0.0):
    """逐行质心追踪; 缺口期间按 pred_slope 预测前进(窗口不冻死); 缺口后重新出现不钳位"""
    PH, PW = maskc.shape
    pts, x, prev_x, prev_had = [], float(x0), None, True
    win = WIN0 * PW
    y = y0
    while (step < 0 and y >= y_end) or (step > 0 and y <= y_end):
        lo, hi = int(max(0, x - win)), int(min(PW, x + win))
        seg = np.nonzero(maskc[y, lo:hi])[0] + lo
        if seg.size:
            xn = float(seg.mean())
            if prev_had and prev_x is not None and abs(xn - prev_x) > MAXDX * PW:
                xn = prev_x
            x, prev_x, prev_had = xn, xn, True
        else:
            x = x + pred_slope          # 缺口: 沿车道斜率预测, 窗口保持在车道上
            prev_had = False
        pts.append((y, x)); y += step
    return pts

def rdp(pts, eps):
    """Ramer-Douglas-Peucker 折线简化: 保留首尾端点 + 几何关键拐点, 删冗余点"""
    pts = [tuple(float(a) for a in p) for p in pts]
    if len(pts) < 3:
        return pts
    start = np.array(pts[0], float); end = np.array(pts[-1], float)
    arr = np.array(pts, float)
    seg = end - start
    norm = np.linalg.norm(seg)
    if norm < 1e-9:
        return [pts[0], pts[-1]]
    ap = start - arr
    cross = seg[0] * ap[:, 1] - seg[1] * ap[:, 0]
    d = np.abs(cross) / norm
    i = int(np.argmax(d))
    if d[i] > eps:
        return rdp(pts[:i + 1], eps)[:-1] + rdp(pts[i:], eps)
    return [pts[0], pts[-1]]

def simplify(pts, target=(4, 5)):
    """从小 eps 往上搜, 取到顶点数落在 target 区间的最小 eps(=清抖动但保留真实弯道)"""
    for eps in range(2, 61, 2):
        s = rdp(pts, eps)
        if target[0] <= len(s) <= target[1]:
            return s, eps
    s = rdp(pts, 20)
    return s, 20

def trim_collinear(pts, thr=10.0):
    """迭代删掉令折线出现局部尖角(外凸/方向反转)的中间顶点: 该点 x 在前后两点间是局部极值
    且到前后连线距离>thr。每轮只删最凸的一个, 删后序列恢复单调即停 -> 只清外凸假点, 留真弯道。pts 为 (y,x)"""
    pts = list(pts)
    while len(pts) > 3:
        worst, wd = None, 0.0
        for i in range(1, len(pts) - 1):
            x0, y0 = pts[i - 1][1], pts[i - 1][0]
            x1, y1 = pts[i][1],     pts[i][0]
            x2, y2 = pts[i + 1][1], pts[i + 1][0]
            is_peak = (x1 < x0 and x1 < x2) or (x1 > x0 and x1 > x2)   # 局部极值=尖角
            if not is_peak:
                continue
            dx, dy = x2 - x0, y2 - y0
            L2 = dx * dx + dy * dy
            if L2 < 1e-9:
                d = 0.0
            else:
                t = ((x1 - x0) * dx + (y1 - y0) * dy) / L2
                px, py = x0 + t * dx, y0 + t * dy
                d = ((x1 - px) ** 2 + (y1 - py) ** 2) ** 0.5
            if d > wd:
                wd, worst = d, i
        if worst is None or wd < thr:
            break
        del pts[worst]
    return pts

def detect(small):
    """核心检测: 返回左/右车道逐行 x 字典 (行号->x, small 分辨率像素)。
    算法与终态版本一致, 未改任何阈值。"""
    PH, PW = small.shape[0], small.shape[1]
    ym, wm = color_masks(small)
    yA, yAr = anchor_bottom(ym, 0.82, 0.92)
    wA, wAr = anchor_bottom(wm, ROI_TOP, 0.92)   # 白线底部可能被车挡, 向上扫到出现的最低行
    if yA is not None and wA is not None:
        d = (wA - yA) / float(PW)
        if not (0.35 <= d <= 0.75):
            # 重选: 距左锚 0.35~0.75W 内最近的白峰
            band = wm[int(0.82 * PH):int(0.92 * PH), :].sum(0).astype(np.float32)
            cand = np.nonzero(band > 0)[0]
            lo, hi = yA + 0.35 * PW, yA + 0.75 * PW
            ok = cand[(cand >= lo) & (cand <= hi)]
            if ok.size:
                wA = int(ok[np.argmax(band[ok])]); wAr = int(0.87 * PH)
    Ld = {}
    if yA is not None:
        for (y, x) in track_dir(ym, yA, yAr, int(ROI_TOP * PH), -1, pred_slope=0.0):
            Ld[y] = x
    # 左线斜率(镜像给右线当缺口预测斜率)
    La = 0.0
    if len(Ld) >= 2:
        a = np.array(sorted(Ld.items()), float)
        La = np.polyfit(a[:, 0], a[:, 1], 1)[0]   # dx/dy
    Rd = {}
    if wA is not None:
        for (y, x) in track_dir(wm, wA, wAr, int(ROI_TOP * PH), -1, pred_slope=La):
            Rd[y] = x
        for (y, x) in track_dir(wm, wA, wAr, int(0.92 * PH) - 1, +1, pred_slope=La):
            Rd[y] = x
    return {'Ld': Ld, 'Rd': Rd, 'PH': PH, 'PW': PW, 'yA': yA, 'wA': wA, 'La': La}

def main():
    global OUT_PTS, OUT_ISO, OUT_CURVE
    t0 = time.time()
    img_path = sys.argv[1] if len(sys.argv) > 1 else IMG
    if len(sys.argv) > 2:
        OUT_PTS = sys.argv[2] + "_pts.png"
        OUT_ISO = sys.argv[2] + "_iso.png"
        OUT_CURVE = sys.argv[2] + "_curve.png"
    img = cv2.imread(img_path)
    if img is None:
        log("IMG NOT FOUND", img_path); sys.exit(2)
    H, W = img.shape[:2]
    if CROP_BOTTOM > 0:
        keep = int(H * (1.0 - CROP_BOTTOM))
        img = img[:keep, :]
        log("crop bottom 1/8 -> keep top %d/%d rows" % (keep, H))
    PH = int(round(H * (PROC_W / float(W))))
    small = cv2.resize(img, (PROC_W, PH), interpolation=cv2.INTER_AREA)
    del img
    log("load+resize -> %dx%d  rss=%.1fMB" % (PROC_W, PH, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6))

    r = detect(small)
    Ld, Rd, PH, PW = r['Ld'], r['Rd'], r['PH'], r['PW']
    ya, wa = r['yA'], r['wA']
    width_str = ("%.2fW" % ((wa - ya) / PW)) if (ya is not None and wa is not None) else "n/a"
    log("anchors yA=%s wA=%s width=%s" % (ya, wa, width_str))
    Lpts = sorted(Ld.items()); Rpts = sorted(Rd.items())

    # ---- 逐行数字诊断 ----
    print("\n=== 逐行诊断 (row : L追踪 / L实际min-max : R追踪 / R实际min-max) ===", flush=True)
    ym, wm = color_masks(small)
    for y in range(int(0.92 * PH) - 1, int(ROI_TOP * PH) - 1, -8):
        ys = np.nonzero(ym[y])[0]; ws = np.nonzero(wm[y])[0]
        lmin, lmax = (int(ys.min()), int(ys.max())) if ys.size else (None, None)
        rmin, rmax = (int(ws.min()), int(ws.max())) if ws.size else (None, None)
        lx, rx = Ld.get(y), Rd.get(y)
        lx_s = ("%6.0f" % lx) if lx is not None else "     --"
        rx_s = ("%6.0f" % rx) if rx is not None else "     --"
        lstr = (lx_s + " / %d-%d" % (lmin, lmax)) if lmin is not None else (lx_s + " / --")
        rstr = (rx_s + " / %d-%d" % (rmin, rmax)) if rmin is not None else (rx_s + " / --")
        lflag = "  <-- 飘" if (lmin is not None and (lx < lmin - 3 or lx > lmax + 3)) else ""
        rflag = "  <-- 飘" if (rmin is not None and (rx < rmin - 3 or rx > rmax + 3)) else ""
        print("%4d: L %-18s%s  | R %-18s%s" % (y, lstr, lflag, rstr, rflag), flush=True)

    vis = small.copy()
    for (y, x) in Lpts:
        cv2.circle(vis, (int(x), int(y)), 2, (0, 255, 255), -1)
    for (y, x) in Rpts:
        cv2.circle(vis, (int(x), int(y)), 2, (255, 120, 255), -1)
    cv2.imwrite(OUT_PTS, vis)
    cv2.imwrite(OUT_ISO, cv2.merge([ym * 255, wm * 255, np.zeros_like(ym)]))

    # ---- 折成"直的就直 / 不硬接远端突出端点"的干净折线 ----
    TRIM_TOP = 0.12
    curve_vis = small.copy()
    for pts, color in ((Lpts, (0, 0, 255)), (Rpts, (255, 120, 200))):
        if len(pts) < 4:
            continue
        n_trim = int(TRIM_TOP * len(pts))
        trimmed = pts[n_trim:]                      # 去掉最顶部(远端)噪点, 干净收尾
        if len(trimmed) < 4:
            trimmed = pts
        c, eps = simplify(trimmed, (4, 5))          # 尽量直: 直线段自然合并, 只留拐点
        c = trim_collinear(c, 8.0)                  # 删掉中间外凸/抖动的冗余顶点(如红色L线第3点)
        arr = np.array([[int(x), int(y)] for (y, x) in c], np.int32).reshape(-1, 1, 2)
        cv2.polylines(curve_vis, [arr], False, color, 3)
        for (y, x) in pts:
            cv2.circle(curve_vis, (int(x), int(y)), 1, color, -1)
        kc = (0, 255, 255) if color[0] == 0 else (255, 255, 0)
        for (y, x) in c:
            cv2.circle(curve_vis, (int(x), int(y)), 3, kc, -1)
        log("curve %s eps=%.0f verts=%d(=%d段) verts(y,x)=%s" % (
            "L" if color[0] == 0 else "R", eps, len(c), len(c) - 1,
            [(int(y), int(x)) for (y, x) in c]))
    cv2.imwrite(OUT_CURVE, curve_vis)
    log("DONE %0.fms  rss=%.1fMB  L=%d R=%d" % ((time.time() - t0) * 1000,
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6, len(Lpts), len(Rpts)))

if __name__ == "__main__":
    main()
