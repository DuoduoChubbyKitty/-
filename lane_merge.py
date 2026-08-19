#!/usr/bin/env python3
"""
lane_merge.py: 合并多个 lane_labels 批次 JSON，按 image 文件名排序。
用法:
    python3 lane_merge.py --out lane_labels.json \
        lane_labels_batch_0.json lane_labels_batch_1.json ...
"""
import json, argparse
from pathlib import Path

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--out', required=True, help='合并输出路径')
    p.add_argument('inputs', nargs='+', help='批次 JSON 文件')
    args = p.parse_args()

    merged = {}
    for path in args.inputs:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for entry in data:
            merged[entry['image']] = entry

    out = sorted(merged.values(), key=lambda e: e['image'])
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'[merged] {len(out)} entries -> {args.out}')

if __name__ == '__main__':
    main()
