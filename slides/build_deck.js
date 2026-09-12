const pptxgen = require("pptxgenjs");
const p = new pptxgen();
p.layout = "LAYOUT_WIDE";                 // 13.3 x 7.5
p.author = "PI-DON reproduction";
p.title = "PI-DON 论文复现";

const NAVY = "21295C", DEEP = "065A82", TEAL = "1C7293";
const INK = "1A1A22", MUT = "5A6472", LINE = "D4DAE2";
const TINT = "EEF3F8", WHITE = "FFFFFF";
const GOOD = "1E7A4B", BAD = "B3261E", WARN = "A8761A";
const CJK = "Microsoft YaHei", MONO = "Consolas";

const T = (s, o) => Object.assign({ isTextBox: true, fontFace: CJK, color: INK, margin: 0 }, o);

// ── numbered badge motif ────────────────────────────────────────────
function badge(s, n, x, y, col) {
  s.addShape(p.ShapeType.ellipse, { x, y, w: 0.34, h: 0.34, fill: { color: col } });
  s.addText(String(n), T(String(n), {
    x, y, w: 0.34, h: 0.34, align: "center", valign: "middle",
    fontSize: 13, bold: true, color: WHITE, fontFace: "Calibri",
  }));
}
function head(s, txt, x, y, w, col) {
  s.addText(txt, T(txt, { x, y, w, h: 0.34, valign: "middle", fontSize: 15, bold: true, color: col }));
}

/* ══════════════════ SLIDE 1 — title ══════════════════ */
{
  const s = p.addSlide();
  s.background = { color: NAVY };
  s.addText("组会汇报 · 2026-09-10 · 论文复现", T("", {
    x: 0.85, y: 0.85, w: 8, h: 0.3, fontSize: 13, color: "9BB4D6", charSpacing: 1,
  }));
  s.addText("物理信息深度算子网络\n用于三维时域电磁建模", T("", {
    x: 0.85, y: 1.35, w: 9.2, h: 1.7, fontSize: 40, bold: true, color: WHITE, lineSpacing: 48,
  }));
  s.addText("Physics-Informed Deep Operator Network for 3-D Time-Domain Electromagnetic Modeling",
    T("", { x: 0.85, y: 3.15, w: 10.2, h: 0.5, fontSize: 13, color: "CADCFC", fontFace: "Calibri", italic: true }));
  s.addText("Y. Qi and C. D. Sarris   ·   IEEE Trans. Microw. Theory Techn., 73(7), 3800–3812, July 2025",
    T("", { x: 0.85, y: 3.62, w: 10.2, h: 0.3, fontSize: 12, color: "8FA6C9", fontFace: "Calibri" }));

  s.addShape(p.ShapeType.roundRect, {
    x: 0.85, y: 4.4, w: 11.6, h: 1.05, rectRadius: 0.06,
    fill: { color: "2E3A73" },
  });
  s.addText([
    { text: "一句话：", options: { bold: true, color: "9BB4D6" } },
    { text: "把 FDTD 时间推进里的空间旋度算子 ∇× 换成一个神经网络，让它一次训练、换网格尺寸不用重训。", options: { color: WHITE } },
  ], T("", { x: 1.15, y: 4.4, w: 11.0, h: 1.05, valign: "middle", fontSize: 15, lineSpacing: 24 }));

  s.addText("本次汇报 = 从零完整复现  +  一处论文没有回答的问题",
    T("", { x: 0.85, y: 5.85, w: 11.6, h: 0.35, fontSize: 14, bold: true, color: "F0C86A" }));

  s.addNotes(
    "开场（约20秒）：\n" +
    "这篇是把 FDTD 里最贵的那一步——空间旋度——换成神经网络。卖点是「算子」：一次训练，换网格尺寸不用重训。\n" +
    "我不是跑作者代码，是从零复现：自己写 FDTD、自己生成数据、自己搭网络。\n\n" +
    "【可能追问】为什么值得复现？\n" +
    "答：FDTD 每一步的代价都在空间差分上。如果算子能学出来并且能换网格复用，那就是把「每个新问题重新算」变成「训一次到处用」，这个立意对我们做天线仿真是直接相关的。"
  );
}

/* ══════════════════ SLIDE 2 — what the paper does / what I built ══════════════════ */
{
  const s = p.addSlide();
  s.background = { color: WHITE };
  s.addText("论文在做什么，我做了什么", T("", {
    x: 0.6, y: 0.42, w: 9, h: 0.6, fontSize: 32, bold: true, color: NAVY,
  }));

  // -- left: the FDTD loop, with the replaced box highlighted
  s.addShape(p.ShapeType.roundRect, { x: 0.6, y: 1.3, w: 5.5, h: 4.9, rectRadius: 0.06, fill: { color: TINT } });
  head(s, "FDTD 的一个时间步", 0.95, 1.5, 4.8, DEEP);

  const steps = [
    ["由 E 算 ∇×E", "→ 更新 H", true],
    ["由 H 算 ∇×H", "→ 更新 E", true],
    ["回到第 1 步，推进下一时刻", "", false],
  ];
  let yy = 2.1;
  steps.forEach(([a, b, hot], i) => {
    const h = 0.72;
    s.addShape(p.ShapeType.roundRect, {
      x: 0.95, y: yy, w: 4.8, h, rectRadius: 0.05,
      fill: { color: hot ? "FDECEA" : WHITE },
      line: { color: hot ? BAD : LINE, width: hot ? 1.4 : 1 },
    });
    badge(s, i + 1, 1.13, yy + 0.19, hot ? BAD : MUT);
    s.addText([
      { text: a, options: { bold: true, color: hot ? BAD : INK } },
      { text: "  " + b, options: { color: MUT } },
    ], T("", { x: 1.6, y: yy, w: 4.0, h, valign: "middle", fontSize: 14 }));
    yy += h + 0.22;
  });

  s.addShape(p.ShapeType.roundRect, { x: 0.95, y: 4.92, w: 4.8, h: 1.1, rectRadius: 0.05, fill: { color: NAVY } });
  s.addText([
    { text: "论文的改动：", options: { bold: true, color: "9BB4D6" } },
    { text: "把红框里的 ∇× 换成一个 DeepONet + 3D U-Net，称作 DCO（深度旋度算子）", options: { color: WHITE } },
  ], T("", { x: 1.2, y: 4.92, w: 4.3, h: 1.1, valign: "middle", fontSize: 12.5, lineSpacing: 18 }));

  // -- right: what I built
  head(s, "我复现的四块（不是跑作者代码）", 6.55, 1.5, 6.2, DEEP);
  const mine = [
    ["自己写 Yee FDTD", "谐振频率对解析解误差 < 0.4%，并用 CST 做了第三方交叉验证 → 基准可信"],
    ["按论文式 (2)(3)(4) 生成训练集", "平面波场 + 对应的旋度，1500 个样本"],
    ["复现 DCO 网络", "DeepONet 双分支 + 3D U-Net，2.25M 参数"],
    ["三组测试", "① 单步精度  ② 换网格尺寸照用  ③ 塞回时间推进跑闭环"],
  ];
  let y2 = 2.05;
  mine.forEach(([t, d], i) => {
    badge(s, i + 1, 6.55, y2 + 0.02, TEAL);
    s.addText(t, T("", { x: 7.05, y: y2, w: 5.7, h: 0.32, fontSize: 14.5, bold: true, color: INK }));
    s.addText(d, T("", { x: 7.05, y: y2 + 0.34, w: 5.7, h: 0.62, fontSize: 12, color: MUT, lineSpacing: 16 }));
    y2 += 1.08;
  });

  s.addText("复现过程中记录了 8 个论文没写、必须自己踩出来的实现细节 —— 后面第 3 页会讲其中最贵的两个。",
    T("", { x: 6.55, y: 6.4, w: 6.2, h: 0.5, fontSize: 11.5, color: WARN, italic: true, lineSpacing: 15 }));

  s.addNotes(
    "（约45秒）\n" +
    "左边：FDTD 每一步就是两次旋度、两次更新。论文把这两次旋度换成同一个网络。\n" +
    "右边：我复现了四块。地基是我自己写的 FDTD，用矩形腔的解析谐振频率校过，误差 0.4% 以内，又用 CST 独立算了一遍对上了——所以后面所有「网络对不对」的判断才有意义。\n\n" +
    "【可能追问1】为什么叫「算子」不叫「网络」？\n" +
    "答：普通网络学的是「这个输入→这个输出」。算子学的是「函数→函数」的映射，所以理论上换了网格分辨率、换了区域尺寸，同一套权重还能用。这正是论文第三个实验要证的事。\n\n" +
    "【可能追问2】DeepONet 的两条分支是什么？\n" +
    "答：branch 分支吃场本身（E 的三个分量），trunk 分支吃「你想在哪里求值」的坐标信息，两条分支的输出做哈达玛积（逐元素相乘）合并。\n\n" +
    "【可能追问3】为什么要 CST 交叉验证？\n" +
    "答：怕自己的 FDTD 写错了却和自己生成的数据「自洽地错」。第三方求解器是独立的一票。"
  );
}

/* ══════════════════ SLIDE 3 — results vs paper ══════════════════ */
{
  const s = p.addSlide();
  s.background = { color: WHITE };
  s.addText("复现结果：对上了哪里，差在哪里", T("", {
    x: 0.6, y: 0.42, w: 9, h: 0.6, fontSize: 32, bold: true, color: NAVY,
  }));

  const rows = [
    [{ text: "比什么", options: { bold: true, color: WHITE, fill: { color: DEEP } } },
     { text: "论文", options: { bold: true, color: WHITE, fill: { color: DEEP } } },
     { text: "我们", options: { bold: true, color: WHITE, fill: { color: DEEP } } },
     { text: "判定", options: { bold: true, color: WHITE, fill: { color: DEEP }, align: "center" } }],
    [{ text: "① 单步精度\n（按论文自洽的算法 nMAE）" },
     { text: "Table I 同一档" },
     { text: "5.7 × 10⁻³", options: { bold: true } },
     { text: "对上", options: { bold: true, color: GOOD, align: "center" } }],
    [{ text: "② 换网格尺寸照用\n（16³ 训练 → 更大网格测）" },
     { text: "4.1 ~ 4.7 × 10⁻³\n（32³ 训练）" },
     { text: "1.9 ~ 4.1 × 10⁻²", options: { bold: true } },
     { text: "差 ~10×", options: { bold: true, color: WARN, align: "center" } }],
    [{ text: "③ 塞回时间推进\n（当 ∇× 用，一步步跑）" },
     { text: "Fig. 7/8 跑通" },
     { text: "第 147 步发散", options: { bold: true } },
     { text: "差", options: { bold: true, color: BAD, align: "center" } }],
  ];
  s.addTable(rows, {
    x: 0.6, y: 1.25, w: 7.35, colW: [2.5, 1.85, 1.85, 1.15],
    rowH: [0.38, 0.72, 0.78, 0.72],
    fontFace: CJK, fontSize: 12, color: INK, valign: "middle",
    border: { type: "solid", color: LINE, pt: 1 }, margin: 0.08,
  });

  // chart: our EXP2 numbers + paper reference
  s.addText("② 的原始数据（相对 L₂ 误差，×10⁻²，越低越好）",
    T("", { x: 8.25, y: 1.25, w: 4.5, h: 0.3, fontSize: 12, bold: true, color: DEEP }));
  s.addChart(p.ChartType.bar, [{
    name: "relative L2",
    labels: ["16³", "32³", "48³", "64×96×16", "32×64×16", "论文 III-D"],
    values: [1.886, 2.450, 4.119, 3.146, 3.139, 0.41],
  }], {
    x: 8.1, y: 1.6, w: 4.7, h: 2.95,
    barDir: "col", chartColors: [TEAL, TEAL, TEAL, TEAL, TEAL, "C0392B"],
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 9,
    dataLabelFormatCode: "0.00", dataLabelFontFace: "Calibri",
    catAxisLabelFontSize: 9, catAxisLabelFontFace: CJK, catAxisLabelColor: MUT,
    valAxisLabelFontSize: 9, valAxisLabelColor: MUT, valAxisMaxVal: 5,
    valGridLine: { color: "E8ECF2", size: 1 }, catGridLine: { style: "none" },
    showLegend: false, barGapWidthPct: 45,
  });
  s.addText("红柱配置与我们不同（论文 32³ 训练），只作量级参照，不是同条件对比。",
    T("", { x: 8.1, y: 4.62, w: 4.7, h: 0.4, fontSize: 10, color: MUT, italic: true, lineSpacing: 13 }));

  s.addShape(p.ShapeType.roundRect, { x: 0.6, y: 4.05, w: 7.35, h: 1.0, rectRadius: 0.05, fill: { color: TINT } });
  s.addText([
    { text: "① 为什么要说「按论文自洽的算法」？  ", options: { bold: true, color: DEEP } },
    { text: "论文式 (5) 的逐点相对误差套在旋度场上会被零点炸掉。我试了三种常见算法，只有「MAE 除以最大值」能让论文自己的 Table I 和第三节 D 互相自洽。", options: { color: INK } },
  ], T("", { x: 0.9, y: 4.05, w: 6.8, h: 1.0, valign: "middle", fontSize: 11.5, lineSpacing: 17 }));

  // callout
  s.addShape(p.ShapeType.roundRect, { x: 0.6, y: 5.25, w: 12.2, h: 1.02, rectRadius: 0.06, fill: { color: "FFF6E5" } });
  s.addText([
    { text: "差距来自哪里？  ", options: { bold: true, color: WARN } },
    { text: "论文没有写明 trunk 的坐标编码和输入归一化方式。我做了消融：这两个开关合起来值 ", options: { color: INK } },
    { text: "17×", options: { bold: true, color: BAD } },
    { text: "。剩下的是训练规模（我们 16³ / 1500 样本 / 单张 GTX 1660）和论文 Algorithm 1 的双循环我还没做完。", options: { color: INK } },
  ], T("", { x: 0.95, y: 5.25, w: 11.5, h: 1.02, valign: "middle", fontSize: 13, lineSpacing: 20 }));

  s.addText("结论：我不认为论文造假 —— 差距可以被规模和论文未写明的实现细节解释完。",
    T("", { x: 0.6, y: 6.45, w: 12.2, h: 0.35, fontSize: 13, bold: true, color: NAVY }));

  s.addNotes(
    "（约60秒，这是最重要的一页）\n" +
    "三行分别是：单步对上了、换网格差 10 倍、闭环 147 步就炸。\n" +
    "先说一个坑：论文报的误差公式是逐点相对误差，直接套在旋度场上会被零点炸掉。我试了三种常见算法，只有 MAE 除以最大值这一种能让论文自己的 Table I 和第三节 D 的数字互相自洽。按那个算法，我们第一行是对上的。\n" +
    "最贵的发现是黄框：论文根本没写 trunk 喂什么坐标、输入怎么归一化。我把这两个开关做了消融，合起来值 17 倍。\n\n" +
    "【可能追问1】17× 是论文里写的吗？\n" +
    "答：不是。论文只说 trunk 输入是「E 和 H 的坐标」，没写具体编码，也没写归一化。17× 是我按 DeepONet 惯例做字面实现，和我改过之后的版本对比出来的。这是复现的发现，不是论文的原话。\n\n" +
    "【可能追问2】那两个开关具体是什么？\n" +
    "答：坐标编码——如果喂绝对位置，16³ 训练时坐标最大 12mm，48³ 推理要到 37.6mm，网络在外推没见过的数；改成只喂 dx,dy,dz 三个常数通道，换网格时 trunk 输入完全不变，维度不变性就是结构上保证的。归一化——除以 max|E| 时，随机场的最大值随体素数增长，16³ 和 48³ 被除以差 18% 的数，输入分布漂了；改成除以 rms 就不漂。\n\n" +
    "【可能追问3】红柱能这么比吗？\n" +
    "答：不能当同条件比，我在图下标注了。论文是 32³ 训练，我们是 16³ 训练，只作量级参照。\n\n" +
    "【可能追问4】那是不是论文在灌水？\n" +
    "答：我的判断是不是。差距能被三件事解释完：训练规模、我没做完 Algorithm 1 的双内层循环、以及论文未写明的实现细节。而且第一行我们是对上的。"
  );
}

/* ══════════════════ SLIDE 4 — the finding ══════════════════ */
{
  const s = p.addSlide();
  s.background = { color: WHITE };
  s.addText("关键发现：闭环能跑多久，不由单步精度决定", T("", {
    x: 0.6, y: 0.42, w: 11, h: 0.6, fontSize: 30, bold: true, color: NAVY,
  }));
  s.addText("「炸掉的步数」指的是时间步，不是训练轮数 —— 权重已经冻住，是拿它当 ∇× 反复调用几百次。",
    T("", { x: 0.6, y: 1.02, w: 11.5, h: 0.3, fontSize: 12, color: MUT, italic: true }));

  const ev = [
    ["七个模型，精度和寿命不相关",
     "最准的那个（147 步）反而不如稍差的那个（168 步）活得久。"],
    ["对照实验：准一倍，早死四成",
     "同一份数据、同一个循环，只换网络的输出方式：\n准一倍的（2.1×10⁻³）活 65 步，差一倍的（4.4×10⁻³）活 108 步。"],
    ["控制变量：固定误差，只改结构",
     "谱半径 1.0211 → 预测 661 步 / 实测 730；\n谱半径 1.0598 → 预测 238 步 / 实测 256。误差 10% 以内。"],
  ];
  let y = 1.55;
  ev.forEach(([t, d], i) => {
    s.addShape(p.ShapeType.roundRect, { x: 0.6, y, w: 7.15, h: 1.42, rectRadius: 0.05, fill: { color: TINT } });
    badge(s, i + 1, 0.9, y + 0.22, DEEP);
    s.addText(t, T("", { x: 1.4, y: y + 0.18, w: 6.1, h: 0.32, fontSize: 15, bold: true, color: INK }));
    s.addText(d, T("", { x: 1.4, y: y + 0.55, w: 6.1, h: 0.8, fontSize: 12, color: MUT, lineSpacing: 17 }));
    y += 1.62;
  });

  // right column: the criterion
  s.addShape(p.ShapeType.roundRect, { x: 8.05, y: 1.55, w: 4.75, h: 4.61, rectRadius: 0.06, fill: { color: NAVY } });
  s.addText("那由什么决定？", T("", { x: 8.4, y: 1.8, w: 4.1, h: 0.35, fontSize: 15, bold: true, color: "9BB4D6" }));
  s.addText("谱半径 ρ", T("", { x: 8.4, y: 2.2, w: 4.1, h: 0.75, fontSize: 40, bold: true, color: WHITE }));
  s.addText("一步递推矩阵的最大特征值模长",
    T("", { x: 8.4, y: 2.95, w: 4.1, h: 0.3, fontSize: 12, color: "CADCFC" }));

  s.addText([
    { text: "闭环是把同一个算子连乘几百次。\n", options: { color: WHITE, breakLine: true } },
    { text: "ρ = 1.005 时，1.005", options: { color: WHITE } },
    { text: "¹⁴⁷", options: { color: WHITE } },
    { text: " ≈ 2.1 —— 再精确的单步也会被指数吃掉。\n", options: { color: WHITE, breakLine: true } },
    { text: "精度决定误差的起点高度，ρ 决定有没有指数放大。", options: { color: "F0C86A", bold: true } },
  ], T("", { x: 8.4, y: 3.40, w: 4.1, h: 1.55, fontSize: 12.5, lineSpacing: 19 }));

  s.addShape(p.ShapeType.roundRect, { x: 8.4, y: 5.15, w: 4.05, h: 0.85, rectRadius: 0.05, fill: { color: "2E3A73" } });
  s.addText("我构造了一个误差大 2.4 倍、但保持结构的算子 —— 跑满 4000 步不炸。",
    T("", { x: 8.62, y: 5.15, w: 3.6, h: 0.85, valign: "middle", fontSize: 12, color: WHITE, lineSpacing: 17 }));

  s.addText("论文展示了它能跑（Fig. 7/8 横轴就是时间步），但没有做稳定性分析 —— 没有给 ρ，也没有说超过展示的步数会怎样。",
    T("", { x: 0.6, y: 6.45, w: 12.2, h: 0.4, fontSize: 13, bold: true, color: NAVY, lineSpacing: 18 }));

  s.addNotes(
    "（约60秒）\n" +
    "我一开始以为闭环炸是精度不够，加大训练就好。三组实验把这个想法证伪了。\n" +
    "第二条最直观：同一份数据、同一个循环，我只换了网络最后一层的输出方式。一种是直接输出旋度；另一种是先输出一个中间矢量场，再对它取精确的离散旋度——后者散度天生为零，单步精度也确实准一倍。结果它反而早死四成。\n" +
    "第三条是真正的控制变量：我固定算子误差、只改结构，谱半径能把发散步数预测到 10% 以内。\n" +
    "道理很朴素：闭环是把算子连乘几百次，起作用的是 ρ 的 147 次方。\n\n" +
    "【可能追问1】谱半径具体是哪个矩阵的？\n" +
    "答：把一整个时间步——两次旋度加两次更新——写成一个线性映射，也就是 6n³ 维的一步递推矩阵，取它最大特征值的模长。我在 6³ 的小网格上把这个矩阵显式建出来直接求特征值。\n\n" +
    "【可能追问2】两个点就下结论会不会太少？\n" +
    "答：所以我没有只靠那两个点。七个模型的精度-寿命散点没有相关性是第一条，那两个头是第二条，第三条才是控制变量实验——固定误差只改结构，预测误差 10% 以内。三条方向一致。\n\n" +
    "【可能追问3】ρ ≤ 1 就一定稳定吗？\n" +
    "答：是在一个有限的 CFL 之下稳定。如果算子放大高波数分量，允许的时间步会变小，CFL 上限被压紧。所以我报的是「在某个 CFL 下 ρ 等于 1」，不是无条件的。\n\n" +
    "【可能追问4】那论文为什么能跑出 Fig.7/8？\n" +
    "答：三种可能，我倾向于都有：一是论文做完了 Algorithm 1 的双内层物理循环，那相当于间接在压 ρ；二是可能只是量的差别——如果它的 ρ 是 1.0005，画 500 步只放大 1.28 倍，图上完全看不出问题；三是训练规模。在有限步数的窗口里，「还没发散」和「稳定」长得一模一样。"
  );
}

/* ══════════════════ SLIDE 5 — my angle ══════════════════ */
{
  const s = p.addSlide();
  s.background = { color: NAVY };
  s.addText("我的切入点：把稳定性写进网络结构，而不是靠训练去凑", T("", {
    x: 0.6, y: 0.5, w: 12, h: 0.6, fontSize: 28, bold: true, color: WHITE,
  }));

  s.addShape(p.ShapeType.roundRect, { x: 0.6, y: 1.3, w: 12.2, h: 0.85, rectRadius: 0.06, fill: { color: "2E3A73" } });
  s.addText([
    { text: "构造：", options: { bold: true, color: "9BB4D6" } },
    { text: "学到的旋度 = 「精确离散旋度」与「一个对称正定滤波器 S」的复合", options: { color: WHITE, bold: true } },
    { text: "   →  复合算子的谱是实的  →  ρ 恒等于 1（可证，不是训出来的）", options: { color: "CADCFC" } },
  ], T("", { x: 0.95, y: 1.3, w: 11.6, h: 0.85, valign: "middle", fontSize: 14, lineSpacing: 20 }));

  const cards = [
    ["二维验证", "8", "个参数", [
      ["误差", "4.9×10⁻⁵", "（Yee 格式 7.3×10⁻²）"],
      ["稳定性", "CFL ≤ 0.70 时 ρ = 1.0000000000", ""],
      ["对照", "同任务的自由 CNN，测到 CFL 0.08 仍然 ρ > 1", ""],
    ]],
    ["三维验证", "12", "个参数", [
      ["误差", "1.9×10⁻²", "（Yee 格式 8.0×10⁻²，好 4.2 倍）"],
      ["稳定性", "CFL 0.70 时 ρ = 1.0000000000", ""],
      ["对照", "CFL 0.99 时 ρ = 1.76，说明 CFL 上限被压紧了", ""],
    ]],
  ];
  cards.forEach(([ttl, num, unit, items], i) => {
    const x = 0.6 + i * 6.3;
    s.addShape(p.ShapeType.roundRect, { x, y: 2.35, w: 5.9, h: 2.75, rectRadius: 0.06, fill: { color: WHITE } });
    s.addText(ttl, T("", { x: x + 0.35, y: 2.55, w: 2.2, h: 0.34, fontSize: 15, bold: true, color: DEEP }));
    s.addText([
      { text: num, options: { fontSize: 26, bold: true, color: TEAL, fontFace: "Calibri" } },
      { text: " " + unit, options: { fontSize: 12, color: MUT } },
    ], T("", { x: x + 3.0, y: 2.5, w: 2.5, h: 0.45, align: "right", valign: "middle" }));
    let yc = 3.05;
    items.forEach(([k, v, note]) => {
      s.addText(k, T("", { x: x + 0.35, y: yc, w: 0.85, h: 0.28, fontSize: 11.5, color: MUT }));
      s.addText([
        { text: v, options: { bold: true, color: INK } },
        { text: note ? "  " + note : "", options: { color: MUT, fontSize: 10.5 } },
      ], T("", { x: x + 1.2, y: yc, w: 4.35, h: 0.28, fontSize: 12, valign: "middle" }));
      yc += 0.62;
    });
  });

  s.addText("下一步", T("", { x: 0.6, y: 5.4, w: 2, h: 0.32, fontSize: 15, bold: true, color: "9BB4D6" }));
  s.addText([
    { text: "①  把论文 Algorithm 1 的双内层物理循环补完，测它的 ρ —— 验证「物理损失是在间接压谱半径」这个猜想。\n", options: { breakLine: true } },
    { text: "②  把结构约束加进 U-Net，让它在保持容量的同时 ρ ≤ 1 —— 这样才能去做真正需要大网络的场合：非均匀介质、材料界面、粗网格等效算子。", options: {} },
  ], T("", { x: 0.6, y: 5.75, w: 12.2, h: 1.1, fontSize: 13.5, color: WHITE, lineSpacing: 22 }));

  s.addNotes(
    "（约45秒，收尾）\n" +
    "既然 ρ 是判据，那就别靠训练去碰运气，直接把它写进结构：让网络学的不是旋度本身，而是一个对称正定的滤波器，再和精确的离散旋度复合。两个对称算子复合还是对称的，对称算子的谱是实的，ρ 就恒等于 1——这是可以证的，不是训出来的。\n" +
    "二维 8 个参数、三维 12 个参数，都比 Yee 格式本身准，而且稳定。同一个任务上放开约束的自由 CNN，我把时间步一路降到 CFL 0.08，ρ 还是大于 1——也就是说减小时间步救不了它。\n\n" +
    "【可能追问1】12 个参数比 2.25M 的 U-Net 好，是不是说明 U-Net 没必要？\n" +
    "答：不能这么说，这两个不是公平对比。均匀自由空间规则网格上的精确旋度本来就是一个平移不变的线性卷积核，自由度就那么十几个——12 个参数够用不是我设计得好，是题目只有 12 个自由度。U-Net 的容量是为「答案不是固定卷积核」的场合准备的。我这个对比能说明的只有一条：这道示范算例区分不出架构好坏。\n\n" +
    "【可能追问2】那你这套方法能推广到非均匀介质吗？\n" +
    "答：现在还不能，这正是第二条下一步。现在的 S 是一个平移不变的滤波器，介质一变就不成立了。要做的是让 S 依赖局部材料参数，同时保持对称正定——对称性是保 ρ 的关键，不能丢。\n\n" +
    "【可能追问3】这算不算否定了论文？\n" +
    "答：不算。论文的立意是对的，结果我也认为是真的。它没回答的是「为什么能稳」，我给出了判据和一个能保证 ρ 恒等于 1 的构造。这是接在它后面的一步，不是推翻它。\n\n" +
    "【可能追问4】谱半径恰好等于 1 意味着什么？\n" +
    "答：意味着能量既不增也不减，误差只线性累积，不会指数放大。这是无耗介质里 Maxwell 方程本来就该有的性质——Yee 格式之所以能稳定跑几十万步，靠的也是这一条。"
  );
}

p.writeFile({ fileName: "PI-DON_复现汇报.pptx" }).then(f => console.log("wrote", f));
