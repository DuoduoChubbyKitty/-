#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Source C: 数学公式先验 (零像素成本)
灭点独立先验 + steer 直连 vehicle_state 曲率。
在归一化坐标 [0,1] (x/W, y/H) 中解析出路缘两条会聚直线:
    x(y) = x0 + (vx - x0) * (y - y0) / (vy - y0)
灭点 V=(vx,vy): vy 固定(屏幕上方), vx = cx + K * steer;
近端锚点 x0 = cx ± lane_half, y0 为屏幕底部归一化行。
steer 来自 AuroraDrive vehicle_state: 曲率 = vehicle_state[1]/5 (训练契约 curvature*5)。
"""
import numpy as np
import cv2
import sys


def source_c(steer, lane_half=0.18, vy=0.18, K=0.15, y0=0.92, cx=0.5):
    """返回 (xL, xR, V)。
    xL/xR 为函数 y_norm -> x_norm，仅在 y_norm >= vy 时几何有意义（灭点以上不画线）。
    steer: 归一化曲率/转向, 来自 vehicle_state[1]/5。"""
    vx = cx + K * steer
    xL0 = cx - lane_half
    xR0 = cx + lane_half

    def xL(y):
        return xL0 + (vx - xL0) * (y - y0) / (vy - y0)

    def xR(y):
        return xR0 + (vx - xR0) * (y - y0) / (vy - y0)

    return xL, xR, (vx, vy)


def demo(out="sourceC_demo.png", W=480, H=312):
    img = np.zeros((H, W, 3), np.uint8)
    vy, y0 = 0.18, 0.92
    for steer, color in ((0.0, (190, 190, 190)), (0.6, (0, 200, 255))):
        xL, xR, V = source_c(steer, vy=vy, y0=y0)
        for y in np.linspace(vy, y0, 50):
            py = int(y * H)
            pxl = int(xL(y) * W)
            pxr = int(xR(y) * W)
            if 0 <= py < H and 0 <= pxl < W:
                cv2.circle(img, (pxl, py), 2, color, -1)
            if 0 <= py < H and 0 <= pxr < W:
                cv2.circle(img, (pxr, py), 2, color, -1)
        cv2.circle(img, (int(V[0] * W), int(V[1] * H)), 4, (0, 255, 0), -1)
        print("[C] steer=%.2f -> 灭点 vx=%.3f (cx+K*steer=%.3f)" % (steer, V[0], 0.5 + 0.15 * steer))
    cv2.imwrite(out, img)
    print("saved", out)


if __name__ == "__main__":
    demo()
