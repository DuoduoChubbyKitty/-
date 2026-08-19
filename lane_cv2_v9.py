#!/usr/bin/env python3
"""
v9.4: color-aware adaptive lane detection (bug-fixed white threshold).
OpenCV HLS channel order is [H, L, S]; white = high L, low S.
Left base from innermost yellow peak; right base from innermost white peak
that satisfies lane-width constraint relative to left base.

detect(img) 返回像素级二次拟合系数 + 锚点，供 fuse.py 做行级融合。
main() 行为与原 v9.4 完全一致（红/橙拟合线 + 底部圆点 + 保存 png）。
"""
import cv2
import numpy as np
import warnings
import sys
from pathlib import Path

SRC = Path("/Users/dupi/Desktop/自动驾驶系统/档案留存/游戏画面_速度测试.png")
OUT = Path("/Users/dupi/Desktop/车道线OpenCV检测.png")


def preprocess(img):
    """颜色法预处理（pre_combo2.py 逻辑）：HSV mask 圈黄/白 → 通道加权+亮度 → 去天空 → 灰度 → 删面积<500小块。
    返回灰度候选图（车道像素亮、背景黑），直接喂 detect 做 histogram+sliding window。"""
    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    yellow = cv2.inRange(hsv, (15, 60, 30), (35, 255, 255))
    white = cv2.inRange(hsv, (0, 0, 130), (179, 100, 255))
    mask = cv2.bitwise_or(yellow, white)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)
    out = np.zeros_like(img)
    out[mask > 0] = img[mask > 0]
    # 通道加权 + 亮度（绿×5 红×1 蓝×1 亮度×2）
    out = out.astype(np.float32)
    out[:, :, 0] = out[:, :, 0] * 1.0   # 蓝
    out[:, :, 1] = out[:, :, 1] * 5.0   # 绿
    out[:, :, 2] = out[:, :, 2] * 1.0   # 红
    out = out * 2.0                     # 亮度
    out = np.clip(out, 0, 255).astype(np.uint8)
    # 去天空 3.2/8
    SKY_FRAC = 3.2 / 8
    out[:int(h * SKY_FRAC), :] = 0
    # 转灰度
    gray = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
    # 删面积<500 的小块（落叶/碎屑）
    _, binar = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY)
    cnts, _ = cv2.findContours(binar, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    mask_keep = np.zeros_like(gray)
    MIN_AREA = 500
    for c in cnts:
        if cv2.contourArea(c) >= MIN_AREA:
            cv2.drawContours(mask_keep, [c], -1, 255, -1)
    gray = cv2.bitwise_and(gray, mask_keep)
    return gray


def detect(img):
    """核心检测：先经 preprocess 得到灰度车道候选，再做 histogram+sliding window 拟合。
    端点系数 (x=a*y^2+b*y+c) + 锚点，供 fuse.py 行级融合。
    分辨率归一化：任意输入尺寸都能跑——小图(如 224x224 录制缩略图)上采样到 TARGET_W，
    保证下游 margin/n_windows 等比例假设成立；返回 scale 供上层把坐标映射回原图。"""
    TARGET_W = 960
    H0, W0 = img.shape[:2]
    scale_x = scale_y = 1.0
    if W0 < TARGET_W:
        s = TARGET_W / float(W0)
        img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)
        scale_x = scale_y = 1.0 / s
    H, W = img.shape[:2]
    gray = preprocess(img)
    binary = (gray > 120).astype(np.uint8) * 255

    # ROI: lower part of image
    roi_top = int(H * 0.55)
    binary[:roi_top, :] = 0

    # mild morphological close to connect dashed segments
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    # ---------- bottom histogram auto base localization ----------
    band_y_low = int(H * 0.82)
    band_y_high = int(H * 0.92)

    def hist_peaks(mask, color_name):
        band = mask[band_y_low:band_y_high, :]
        hist = np.sum(band, axis=0).astype(np.float32)
        if hist.max() == 0:
            return [], hist
        hist_s = cv2.GaussianBlur(hist.reshape(1, -1), (1, 31), 0).ravel()
        maxv = hist_s.max()
        min_h = maxv * 0.10 if maxv > 50 else 20
        peaks = []
        for i in range(1, W - 1):
            if hist_s[i] > hist_s[i - 1] and hist_s[i] > hist_s[i + 1] and hist_s[i] >= min_h:
                peaks.append(i)
        merged = []
        min_sep = int(W * 0.04)
        for p in sorted(peaks):
            if merged and p - merged[-1] < min_sep:
                if hist_s[p] > hist_s[merged[-1]]:
                    merged[-1] = p
            else:
                merged.append(p)
        print(f"{color_name} peaks={merged} heights={[int(hist_s[p]) for p in merged]}")
        return merged, hist_s

    peaks, _ = hist_peaks(binary, "LANE")

    center = W / 2

    # left base: innermost lane peak left of center
    left_base = None
    if peaks:
        left_candidates = [p for p in peaks if p < center * 0.95]
        if left_candidates:
            left_base = min(left_candidates, key=lambda p: abs(p - center))
        else:
            left_base = min(peaks, key=lambda p: abs(p - center))

    # right base: innermost peak right of left_base with reasonable lane width
    right_base = None
    if peaks and left_base is not None:
        min_sep = int(W * 0.18)
        max_sep = int(W * 0.75)
        right_candidates = [
            p for p in peaks
            if p > left_base and min_sep <= (p - left_base) <= max_sep
        ]
        if right_candidates:
            right_base = min(right_candidates, key=lambda p: p - left_base)
        else:
            fallback = [p for p in peaks if p > center]
            if fallback:
                right_base = min(fallback, key=lambda p: abs(p - center))

    if left_base is None or right_base is None:
        return {'left_fit': None, 'right_fit': None,
                'left_base': left_base, 'right_base': right_base,
                'roi_top': roi_top, 'H': H, 'W': W,
                'scale_x': scale_x, 'scale_y': scale_y, 'work_img': img}

    lane_sep = right_base - left_base
    print(f"bases -> left={left_base}({left_base/W:.3f}w)  "
          f"right={right_base}({right_base/W:.3f}w)  sep={lane_sep/W:.3f}w")

    # ---------- sliding window tracking upward ----------
    def sliding_window(binary_img, base_x, n_windows=14, margin=50):
        h, w = binary_img.shape
        win_h = h // n_windows
        cur_x = base_x
        xs, ys = [], []
        for i in range(n_windows):
            y_low_w = h - (i + 1) * win_h
            y_high_w = h - i * win_h
            x_low = max(0, cur_x - margin)
            x_high = min(w, cur_x + margin)
            window = binary_img[y_low_w:y_high_w, x_low:x_high]
            nz = np.nonzero(window)
            if len(nz[1]) > 8:
                cur_x = x_low + int(np.mean(nz[1]))
                xs.extend((x_low + nz[1]).tolist())
                ys.extend((y_low_w + nz[0]).tolist())
        return np.array(xs, dtype=np.float32), np.array(ys, dtype=np.float32)

    left_x, left_y = sliding_window(binary, left_base)
    right_x, right_y = sliding_window(binary, right_base)
    print(f"left points={len(left_x)}  right points={len(right_x)}")

    def fit_coeffs(xs, ys):
        if len(xs) < 30:
            print("too few points for fit")
            return None
        yn = ys / H  # 归一化 y 避免高次项病态
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            return np.polyfit(yn, xs, 2)

    left_fit = fit_coeffs(left_x, left_y)
    right_fit = fit_coeffs(right_x, right_y)
    return {'left_fit': left_fit, 'right_fit': right_fit,
            'left_pts': (left_x, left_y), 'right_pts': (right_x, right_y),
            'left_base': left_base, 'right_base': right_base,
            'roi_top': roi_top, 'H': H, 'W': W,
            'scale_x': scale_x, 'scale_y': scale_y, 'work_img': img}


def fit_segments(xs, ys, roi_top, H, n_seg=4, deg=2, min_pts=15):
    """把一条线的点按 y 均分成 n_seg 段，每段独立拟合成曲线。
    返回 [(coeffs, yl, yh), ...]，coeffs 为 x = a*yn^2 + b*yn + c（yn 为段内归一化 [0,1]）。
    点不足的段借用相邻有值段的形状，保证整条线连续可画。"""
    order = np.argsort(ys)
    ys = ys[order]; xs = xs[order]
    y_edges = np.linspace(roi_top, H, n_seg + 1)
    raw = []
    for k in range(n_seg):
        yl, yh = y_edges[k], y_edges[k + 1]
        m = (ys >= yl - 1) & (ys <= yh + 1)
        xm, ym = xs[m], ys[m]
        if len(xm) >= min_pts:
            yn = (ym - yl) / (yh - yl)
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                coeffs = np.polyfit(yn, xm, deg)
            raw.append([coeffs, yl, yh])
        else:
            raw.append([None, yl, yh])
    # 点不足段：借相邻有值段的形状
    for k in range(n_seg):
        if raw[k][0] is None:
            for d in range(1, n_seg):
                if k - d >= 0 and raw[k - d][0] is not None:
                    raw[k][0] = raw[k - d][0]; break
                if k + d < n_seg and raw[k + d][0] is not None:
                    raw[k][0] = raw[k + d][0]; break
    return [(c, yl, yh) for c, yl, yh in raw if c is not None]


def draw_segments(out, segs, color, thickness=16):
    """逐段画曲线（每段独立 polyline，段间留 1px 缝隙以体现“4 段”结构）。"""
    for coeffs, yl, yh in segs:
        a, b, c = coeffs
        yv = np.linspace(yl, yh, 50)
        yn = (yv - yl) / (yh - yl)
        xv = (a * yn ** 2 + b * yn + c).astype(np.int32)
        if not np.all(np.isfinite(xv)):
            continue
        pts = np.stack([xv, yv.astype(np.int32)], axis=1).reshape(-1, 1, 2)
        cv2.polylines(out, [pts], False, color, thickness)


def fit_smooth(xs, ys, roi_top, H, deg=3):
    """单条全局平滑曲线：整条点云拟合 deg 次多项式。
    yn 归一化到 [0,1]（区间 [roi_top, H]），避免高次项病态；结构上不会拐回头。"""
    if len(xs) < 30:
        return None
    yn = (ys - roi_top) / max(1, (H - roi_top))
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        return np.polyfit(yn, xs, deg)


def draw_smooth(out, coeffs, roi_top, H, color, thickness=16, n=200):
    if coeffs is None:
        return
    yv = np.linspace(roi_top, H - 1, n, dtype=np.int32)
    yn = (yv - roi_top) / max(1, (H - roi_top))
    xv = np.polyval(coeffs, yn).astype(np.int32)
    if not np.all(np.isfinite(xv)):
        return
    pts = np.stack([xv, yv], axis=1).reshape(-1, 1, 2)
    cv2.polylines(out, [pts], False, color, thickness)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else str(SRC)
    out_path = sys.argv[2] if len(sys.argv) > 2 else str(OUT)
    img = cv2.imread(src)
    if img is None:
        print(f"FAIL read {SRC}", file=sys.stderr)
        sys.exit(1)
    H, W = img.shape[:2]
    print(f"image {W}x{H}")

    r = detect(img)
    left_fit, right_fit = r['left_fit'], r['right_fit']
    left_base, right_base = r['left_base'], r['right_base']
    roi_top = r['roi_top']

    if left_fit is None or right_fit is None or r.get('left_pts') is None:
        print("MISSING fit")
        cv2.imwrite(out_path, img)
        sys.exit(0)

    left_x, left_y = r['left_pts']
    right_x, right_y = r['right_pts']

    out = r.get('work_img', img).copy()

    # 每条线单条全局平滑曲线（用户定：一段曲线，不用 4 段）
    left_fit = fit_smooth(left_x, left_y, roi_top, H, deg=3)
    right_fit = fit_smooth(right_x, right_y, roi_top, H, deg=3)
    print(f"left fit={'OK' if left_fit is not None else 'FAIL'}  "
          f"right fit={'OK' if right_fit is not None else 'FAIL'}")
    draw_smooth(out, left_fit, roi_top, H, (0, 255, 255))   # 左：黄色
    draw_smooth(out, right_fit, roi_top, H, (0, 0, 255))    # 右：红色

    cv2.circle(out, (left_base, H - 10), 20, (0, 255, 255), -1)
    cv2.circle(out, (right_base, H - 10), 20, (0, 0, 255), -1)

    cv2.imwrite(out_path, out)
    print(f"saved {out_path}")


if __name__ == "__main__":
    main()
