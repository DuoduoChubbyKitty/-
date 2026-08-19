#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fuse.py: 三源行级加权融合 (A 45% / B 45% / C 10%)
- A: 颜色法 v9.4 (detect 返回二次拟合系数)
- B: 几何法 sourceB (detect 返回逐行 x 字典)
- C: 公式先验 sourceC (source_c 返回会聚直线函数, 灭点独立 + steer 直连)

坐标系: 全部归一到 [0,1] (x/W, y/H), 与处理分辨率无关。
融合行: 取 A/B 有效行并集; C 始终参与(独立兜底), A/B 缺失时权重重归一化。
输出: 480 宽融合曲线 png + 逐行数字诊断 (验证远端被 C 拉向会聚)。
"""
import sys, time, resource
import numpy as np
import cv2

import lane_cv2_v9 as A
import lane_geom_sourceB as B
import sourceC as C

IMG = "档案留存/游戏画面_速度测试.png"
PROC_W = 480
W_A, W_B, W_C = 0.45, 0.45, 0.10
LANE_HALF = 0.18      # 近端车道半宽 (归一化, 待标定)
VY = 0.18             # 灭点归一化纵向 (待标定)
K = 0.15              # 灭点横向偏移系数 (steer=1 -> 偏移 0.15W, 待标定)
Y0 = 0.92             # 近端锚点归一化纵向
OUT = "lane_fused.png"


def make_interp(d):
    """把 B 的逐行 x 字典变成线性插值函数 (输入像素行号, 返回像素 x 或 None)。"""
    if not d:
        return lambda yq: None
    ys = np.array(sorted(d.keys()), float)
    xs = np.array([d[y] for y in ys], float)
    def f(yq):
        if yq < ys[0] or yq > ys[-1]:
            return None
        return float(np.interp(yq, ys, xs))
    return f


def main(steer=0.0, points_only=False):
    t0 = time.time()
    img = cv2.imread(IMG)
    if img is None:
        print("FAIL read", IMG, file=sys.stderr); sys.exit(2)
    H, W = img.shape[:2]

    # ---------- Source A (颜色法, 原分辨率) ----------
    ra = A.detect(img)
    Ha, Wa = ra['H'], ra['W']
    a_ytop = ra['roi_top'] / Ha
    aL, aR = ra['left_fit'], ra['right_fit']
    def xA_L(yn):
        y = yn * Ha
        return (aL[0] * y * y + aL[1] * y + aL[2]) / Wa
    def xA_R(yn):
        y = yn * Ha
        return (aR[0] * y * y + aR[1] * y + aR[2]) / Wa
    print("[fuse] A roi_top=%.3f  fit=%s" % (a_ytop, (aL is not None, aR is not None)))

    # ---------- Source B (几何法, 降分辨率) ----------
    PH = int(round(H * (PROC_W / float(W))))
    small = cv2.resize(img, (PROC_W, PH), interpolation=cv2.INTER_AREA)
    rb = B.detect(small)
    Ld, Rd, PBW = rb['Ld'], rb['Rd'], rb['PW']
    b_ytop = B.ROI_TOP
    iL, iR = make_interp(Ld), make_interp(Rd)
    print("[fuse] B ytop=%.3f  nL=%d nR=%d" % (b_ytop, len(Ld), len(Rd)))

    # ---------- Source C (公式先验, 独立灭点 + steer) ----------
    xC_L, xC_R, V = C.source_c(steer, lane_half=LANE_HALF, vy=VY, K=K, y0=Y0)
    print("[fuse] C 灭点 V=(%.3f,%.3f) steer=%.3f" % (V[0], V[1], steer))

    # ---------- 融合行网格 ----------
    y_top = max(a_ytop, b_ytop)
    y_bot = min(1.0, Y0, 0.92)
    rows = np.linspace(y_top, y_bot, 48)
    print("[fuse] 融合行范围 y=[%.3f, %.3f] 共%d行" % (y_top, y_bot, len(rows)))

    fused_L, fused_R = [], []
    print("\n=== 融合逐行诊断 (yn : A_L / B_L / C_L -> 融合L | A_R / B_R / C_R -> 融合R) ===")
    for yn in rows:
        # A
        aAv = 1 if (aL is not None and aR is not None and yn >= a_ytop) else 0
        xaL = xA_L(yn) if aAv else 0.0
        xaR = xA_R(yn) if aAv else 0.0
        # B
        bl = iL(yn * PH)
        br = iR(yn * PH)
        bAv = 1 if (bl is not None and br is not None) else 0
        xbL = (bl / PBW) if bAv else 0.0
        xbR = (br / PBW) if bAv else 0.0
        # C (独立兜底, [VY,Y0] 内恒有效)
        cAv = 1 if (VY <= yn <= Y0) else 0
        xcL = xC_L(yn) if cAv else 0.0
        xcR = xC_R(yn) if cAv else 0.0

        wL = W_A * aAv + W_B * bAv + W_C * cAv
        wR = W_A * aAv + W_B * bAv + W_C * cAv
        fL = (W_A * aAv * xaL + W_B * bAv * xbL + W_C * cAv * xcL) / wL if wL > 0 else None
        fR = (W_A * aAv * xaR + W_B * bAv * xbR + W_C * cAv * xcR) / wR if wR > 0 else None
        if fL is None or fR is None:
            continue
        fused_L.append((yn, fL))
        fused_R.append((yn, fR))
        al = ("%.3f" % xaL) if aAv else "  -- "
        ar = ("%.3f" % xaR) if aAv else "  -- "
        bls = ("%.3f" % xbL) if bAv else "  -- "
        brs = ("%.3f" % xbR) if bAv else "  -- "
        print("%5.3f: %s / %s / %s -> %.3f | %s / %s / %s -> %.3f" % (
            yn, al, bls, ("%.3f" % xcL), fL, ar, brs, ("%.3f" % xcR), fR))

    # ---------- 可视化 (480x312, 内存安全) ----------
    vis = small.copy()
    # C (黄) 公式先验点云
    for yn in np.linspace(VY, Y0, 40):
        py = int(yn * PH)
        cv2.circle(vis, (int(xC_L(yn) * PROC_W), py), 2, (0, 215, 255), -1)
        cv2.circle(vis, (int(xC_R(yn) * PROC_W), py), 2, (0, 215, 255), -1)
    # A (红) 拟合采样点云 (诊断 A 锚点是否偏)
    if aAv:
        for yn in rows:
            py = int(yn * PH)
            cv2.circle(vis, (int(xA_L(yn) * PROC_W), py), 2, (60, 60, 255), -1)
            cv2.circle(vis, (int(xA_R(yn) * PROC_W), py), 2, (60, 60, 255), -1)
    # B (青) 原点云
    for (y, x) in sorted(Ld.items()):
        cv2.circle(vis, (int(x), int(y)), 2, (255, 255, 0), -1)
    for (y, x) in sorted(Rd.items()):
        cv2.circle(vis, (int(x), int(y)), 2, (255, 255, 0), -1)
    # 图例
    cv2.putText(vis, "RED=A颜色法", (6, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (60, 60, 255), 1)
    cv2.putText(vis, "CYAN=B几何法", (6, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1)
    cv2.putText(vis, "YEL=C公式", (6, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 215, 255), 1)
    # 融合 (绿, 粗) —— 仅非 point-cloud 模式
    if not points_only and fused_L:
        arrL = np.array([[int(x * PROC_W), int(yn * PH)] for (yn, x) in fused_L], np.int32).reshape(-1, 1, 2)
        arrR = np.array([[int(x * PROC_W), int(yn * PH)] for (yn, x) in fused_R], np.int32).reshape(-1, 1, 2)
        cv2.polylines(vis, [arrL], False, (0, 255, 0), 3)
        cv2.polylines(vis, [arrR], False, (0, 255, 0), 3)
    out = "lane_points_only.png" if points_only else OUT
    cv2.imwrite(out, vis)
    print("\n[fuse] DONE %.0fms rss=%.1fMB saved %s" % (
        (time.time() - t0) * 1000, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6, out))

    # 远端收敛性检查: 融合线在顶部(y小)与底部(y大)的横向间距应随 y 减小而收窄
    if len(fused_L) >= 2 and len(fused_R) >= 2:
        top = fused_L[0][0]; bot = fused_L[-1][0]
        sep_top = abs(fused_R[0][1] - fused_L[0][1])
        sep_bot = abs(fused_R[-1][1] - fused_L[-1][1])
        print("[check] 远端(y=%.3f)车道宽=%.3fW  近端(y=%.3f)车道宽=%.3fW  收敛=%s" % (
            top, sep_top, bot, sep_bot, "OK" if sep_top < sep_bot else "FAIL"))


if __name__ == "__main__":
    s = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0
    pts = (len(sys.argv) > 2 and sys.argv[2] == "points")
    main(s, pts)
