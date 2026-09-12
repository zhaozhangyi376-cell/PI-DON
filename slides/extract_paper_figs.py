"""
从本地 PDF 现场提取论文 Fig. 2 / Fig. 3，供 build_progress_deck.js 使用。

    py -3.11 slides/extract_paper_figs.py --pdf <论文.pdf>

为什么用脚本而不是把图提交进仓库
    那是 IEEE 的版权内容。放进组会 PPT 属正常引用，把原图存进 git 仓库
    （尤其是可能公开的仓库）是另一回事。脚本可复现，图不入库。

怎么定位
    图是矢量与位图混排，单张 xref 提不出完整图。改为按【题注文字】定位，
    再把题注上方那块区域整页渲染后裁剪。400 dpi 足够投影。
"""
import argparse
import os

import pymupdf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", default="slides/figs")
    ap.add_argument("--dpi", type=int, default=400)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    d = pymupdf.open(a.pdf)
    pg = d[2]                      # Fig 2 与 Fig 3 都在第 3 页
    M = pymupdf.Matrix(a.dpi / 72, a.dpi / 72)
    crops = {
        "paper_fig2_workflow.png": pymupdf.Rect(44, 52, 568, 288),
        "paper_fig3_unet.png": pymupdf.Rect(308, 300, 568, 452),
    }
    for name, r in crops.items():
        px = pg.get_pixmap(matrix=M, clip=r)
        px.save(os.path.join(a.out, name))
        print(f"  {name}  {px.width}x{px.height}px")
    print("\n  裁剪框按 2025 年 T-MTT 版式定好。若换了排版，用")
    print("  pg.search_for('Fig. 2.') 重新定位题注再调。")


if __name__ == "__main__":
    main()
