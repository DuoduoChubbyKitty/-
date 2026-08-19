import cv2, numpy as np

SRC = "/Users/dupi/Desktop/自动驾驶系统/档案留存/游戏画面_速度测试.png"
img = cv2.imread(SRC)
H, W = img.shape[:2]
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
V = hsv[:, :, 2].astype(int)
S = hsv[:, :, 1].astype(int)

# 严格白线 mask（与 pre_combo2 一致）
white_strict = cv2.inRange(hsv, (0, 0, 160), (179, 50, 255))

# 宽松"疑似白线"定义：亮度够 + 饱和度不太高（能兜住被染色的整条线）
loose = (V > 120) & (S < 120)

# 右半屏 + 去天空
sky = int(H * 3 / 8)
band = slice(sky, H)
xs_loose = np.where(loose[band, W // 2:] > 0)[1] + W // 2
if len(xs_loose) == 0:
    print("右半屏没找到疑似白线")
else:
    x0, x1 = int(xs_loose.min()), int(xs_loose.max())
    print(f"右白线 x 范围: {x0}~{x1}  ({x0/W:.3f}W ~ {x1/W:.3f}W)")
    ymid = (sky + H) // 2
    for label, ysl in [("近半(下半, y>mid)", slice(ymid, H)),
                       ("远半(上半, y<mid)", slice(sky, ymid))]:
        sub_loose = loose[ysl, x0:x1 + 1]
        sub_strict = white_strict[ysl, x0:x1 + 1] > 0
        n_loose = int(sub_loose.sum())
        n_pass = int((sub_loose & sub_strict).sum())
        n_fail = n_loose - n_pass
        fail_S = S[ysl, x0:x1 + 1][sub_loose & (~sub_strict)]
        fail_V = V[ysl, x0:x1 + 1][sub_loose & (~sub_strict)]
        s_fail = f"平均S={fail_S.mean():.1f}(最大{fail_S.max()})" if fail_S.size else "无"
        v_fail = f"平均V={fail_V.mean():.1f}(最小{fail_V.min()})" if fail_V.size else "无"
        print(f"[{label}] 疑似白线像素={n_loose}  通过严格mask={n_pass}  被滤={n_fail}")
        if n_fail:
            print(f"          被滤原因: S>50? {s_fail} | V<160? {v_fail}")

# 输出严格白线 mask 单图，方便肉眼看哪半没了
cv2.imwrite("/Users/dupi/Desktop/自动驾驶系统/diag_white_only.png",
            cv2.cvtColor(white_strict, cv2.COLOR_GRAY2BGR))
print("saved diag_white_only.png")
