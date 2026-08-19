import cv2, numpy as np

g = cv2.imread("/Users/dupi/Desktop/自动驾驶系统/pre_combo2.png", 0)
H, W = g.shape
_, binar = cv2.threshold(g, 10, 255, cv2.THRESH_BINARY)
cnts, _ = cv2.findContours(binar, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
info = []
for c in cnts:
    x, y, w, h = cv2.boundingRect(c)
    area = cv2.contourArea(c)
    aspect = max(w, h) / max(1, min(w, h))
    info.append((area, w, h, aspect, x + w // 2, y + h // 2))
info.sort(reverse=True)
print(f"总连通块={len(info)}  阈值候选 ASPECT_MIN 下各保留数：")
for asp_t in [2.5, 3.0, 4.0, 5.0]:
    keep = sum(1 for (a, w, h, asp, cx, cy) in info if asp >= asp_t)
    print(f"  ASPECT_MIN={asp_t}: 保留(细长)={keep}  删除={len(info)-keep}")
print("\n最大的 15 个块（面积, w×h, 长宽比, 中心x, 中心y）：")
for (a, w, h, asp, cx, cy) in info[:15]:
    tag = "车道线?" if asp >= 3 else ("落叶毯?" if a > 5000 else "小落叶?")
    print(f"  area={a:8.0f}  {w}×{h}  asp={asp:5.2f}  cx={cx:4d} cy={cy:4d}  -> {tag}")
