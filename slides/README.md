# slides/ — PPT 与图的生成脚本

## 为什么这里只有脚本没有图

`figs/` 被 gitignore。两个原因：

1. **论文原图是 IEEE 版权内容**（`paper_fig2_workflow.png` / `paper_fig3_unet.png`）。
   放进组会 PPT 属正常引用，存进可能公开的 git 仓库是另一回事。
   用 `extract_paper_figs.py` 从**本地 PDF** 现场提取。
2. 其余的图都是脚本从仓库里的真实数据算出来的，随时能重生成，没必要入库。

## 重新生成全部内容（新 clone 后第一次要跑这个）

```bash
# 1. 从本地论文 PDF 提取 Fig 2 / Fig 3（P1、P2 用）
py -3.11 extract_paper_figs.py --pdf "路径\PhysicsInformed_Deep_Operator_Network....pdf"

# 2. 生成数据图（从仓库里的 *_hist.json / spectral_*.json / pidon_solve_random.json 算）
cd slides
py -3.11 make_p3_p4_figs.py          # P3 训练曲线、P4 发散曲线
py -3.11 make_p5_evidence_figs.py    # P5 三张证据图，直接 import verify_claims 现场重算
py -3.11 make_p5_progress_fig.py     # P5 顶部结果对比图

# 3. 生成 PPT（需要 node）
npm install pptxgenjs
node build_progress_deck.js          # -> PI-DON_复现进展_5页.pptx
```

缺第 1 步会报 `Unable to read media: "figs/paper_fig2_workflow.png"`，这是预期行为。

## 各脚本

| 脚本 | 产出 |
|---|---|
| `build_progress_deck.js` | **当前在用的 5 页进展汇报** |
| `build_deck.js` / `build_repro_section.js` | 更早的版本，留档 |
| `make_p5_evidence_figs.py` | 证据图。**直接 `import verify_claims`**，调用算 `RESULTS.md` 结论的同一段代码，所以图和结论必然对得上号 —— 新画证据图请照此办理 |
| `make_p3_p4_figs.py` | 训练曲线 / 发散曲线，数据来自仓库里的 json |
| `make_p5_progress_fig.py` | 顶部结果对比（精度落点 + 闭环步数） |
| `make_slide_figs.py` | 早期 8 张教学图 |
| `extract_paper_figs.py` | 从论文 PDF 按题注定位裁剪 Fig 2 / Fig 3 |

## 字体的坑

matplotlib 里**中文和数字要分开配字体**：

```python
"font.family": "sans-serif",
"font.sans-serif": ["WenQuanYi Zen Hei", "DejaVu Sans"],   # 中文用前者，数字/负号用后者
"axes.unicode_minus": False,
```

直接把 `font.family` 设成中文字体，负号（U+2212）在该字体里没有字形，
科学计数法的指数会渲染成方块乱码（曾出现过 `10¤4`）。
对数坐标轴的刻度还会绕过这个设置用 mathtext，需要额外用
`FuncFormatter` 换成纯文本刻度，或 `NullLocator` 直接不画。
