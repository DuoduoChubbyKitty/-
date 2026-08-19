#!/usr/bin/env python3
"""
lane_verify.py: 把 lane_labels.json 的标注画到原图上，生成叠加可视化，方便抽查。
用法:
    python3 lane_verify.py lane_labels.json --frames data/raw_clips/clip_20260817_124937/frames --out lane_vis --max 200
"""
import json, os, argparse, math
from pathlib import Path
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as e:
    raise SystemExit("缺少 Pillow，请执行: pip3 install Pillow") from e

COLORS = {
    'left':  ['#ff0000', '#ff6600', '#ffaa00', '#ffcc00'],   # 左4条线由近到远
    'right': ['#00ccff', '#0099ff', '#0066ff', '#0000ff'],   # 右4条线由近到远
}

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('json', help='lane_labels.json 路径')
    p.add_argument('--frames', required=True, help='原始帧目录')
    p.add_argument('--out', default='lane_vis', help='输出目录')
    p.add_argument('--max', type=int, default=200, help='最多处理多少张（0=全部）')
    p.add_argument('--sheet', action='store_true', help='是否生成联系表 contact_sheet.jpg')
    p.add_argument('--cols', type=int, default=4, help='联系表每行几列')
    return p.parse_args()

def draw_frame(img_path, entry, draw):
    W, H = entry['width'], entry['height']
    for side, color_list in COLORS.items():
        segs = entry.get(side, [None]*4)
        for i, seg in enumerate(segs[:4]):
            if seg is None:
                continue
            x1, y1, x2, y2 = seg
            # 归一化 -> 像素
            x1p, y1p = x1 * W, y1 * H
            x2p, y2p = x2 * W, y2 * H
            draw.line([(x1p, y1p), (x2p, y2p)], fill=color_list[i], width=3)
            mx, my = (x1p+x2p)/2, (y1p+y2p)/2
            draw.text((mx+4, my-4), str(i+1), fill='#ffffff')

def main():
    args = parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = Path(args.frames)

    with open(args.json, 'r', encoding='utf-8') as f:
        labels = json.load(f)

    if args.max > 0:
        labels = labels[:args.max]

    sheet_images = []
    for entry in labels:
        name = entry['image']
        img_path = frames_dir / name
        if not img_path.exists():
            print(f'[skip] frame not found: {name}')
            continue
        img = Image.open(img_path).convert('RGB')
        draw = ImageDraw.Draw(img)
        draw_frame(img_path, entry, draw)
        out_path = out_dir / name
        img.save(out_path, quality=95)
        if args.sheet:
            sheet_images.append(img.copy())
        print(f'[ok] {name}')

    if args.sheet and sheet_images:
        cols = args.cols
        rows = math.ceil(len(sheet_images)/cols)
        thumb_w, thumb_h = 320, 180
        sheet = Image.new('RGB', (cols*thumb_w, rows*thumb_h), '#222')
        for i, im in enumerate(sheet_images):
            im.thumbnail((thumb_w, thumb_h))
            x, y = (i % cols)*thumb_w, (i // cols)*thumb_h
            sheet.paste(im, (x, y))
        sheet_path = out_dir / 'contact_sheet.jpg'
        sheet.save(sheet_path, quality=90)
        print(f'[sheet] {sheet_path}')

    print(f'[done] 输出到 {out_dir}')

if __name__ == '__main__':
    main()
