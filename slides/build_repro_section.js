const pptxgen = require("pptxgenjs");
const p = new pptxgen();
p.layout = "LAYOUT_WIDE";
p.title = "PI-DON 复现";

const NAVY = "1E4465", INK = "344654", MUT = "6F7F8E";
const TINT = "F2F6F9", WHITE = "FFFFFF";
const GREEN = "3E8D6D", TEAL = "16A8B7", PALE = "E2F4F6";
const CHIPBG = "FBEEDD", ORANGE = "D9822D", CALLBG = "FEEFDA";
const RED = "B3392B";
const CJK = "微软雅黑";
const F = "/home/user/HFSS_auto/pidon_mvp/slides/figs/";

let PAGE = 9;
const T = (o) => Object.assign({ isTextBox: true, fontFace: CJK, color: INK, margin: 0 }, o);

function frame(s, chip, title, sub) {
  s.background = { color: WHITE };
  s.addShape(p.ShapeType.roundRect, { x: 0.55, y: 0.34, w: 1.35, h: 0.3,
    rectRadius: 0.14, fill: { color: CHIPBG } });
  s.addText(chip, T({ x: 0.55, y: 0.34, w: 1.35, h: 0.3, align: "center",
    valign: "middle", fontSize: 10.5, bold: true, color: ORANGE }));
  s.addText(title, T({ x: 0.55, y: 0.74, w: 12.2, h: 0.52, fontSize: 26,
    bold: true, color: NAVY }));
  if (sub) s.addText(sub, T({ x: 0.55, y: 1.28, w: 12.2, h: 0.28,
    fontSize: 11.5, color: MUT }));
  s.addText(String(PAGE++), T({ x: 12.5, y: 6.98, w: 0.45, h: 0.24,
    fontSize: 10, color: "9AA6B2", align: "right" }));
}
function badge(s, n, x, y, col, d) {
  d = d || 0.32;
  s.addShape(p.ShapeType.ellipse, { x, y, w: d, h: d, fill: { color: col } });
  s.addText(String(n), T({ x, y, w: d, h: d, align: "center", valign: "middle",
    fontSize: 13, bold: true, color: WHITE, fontFace: "Arial" }));
}
function card(s, x, y, w, h, fill) {
  s.addShape(p.ShapeType.roundRect, { x, y, w, h, rectRadius: 0.045,
    fill: { color: fill || TINT } });
}
function strip(s, y, runs, bg, h) {
  h = h || 0.86;
  s.addShape(p.ShapeType.roundRect, { x: 0.55, y, w: 12.25, h,
    rectRadius: 0.05, fill: { color: bg || CALLBG } });
  s.addText(runs, T({ x: 0.95, y, w: 11.5, h, valign: "middle", fontSize: 13,
    lineSpacing: 19 }));
}
function cap(s, txt, x, y, w) {
  s.addText(txt, T({ x, y, w, h: 0.26, fontSize: 10.5, italic: true,
    color: MUT, align: "center" }));
}

/* ═════════ P9 · 总览 ═════════ */
{
  const s = p.addSlide();
  frame(s, "复现 · 总览", "我从零复现了四块",
        "不是跑作者代码 —— FDTD、训练数据、网络、测试，四块全部自己写。后面每块各一页。");

  s.addImage({ path: F + "A_loop.png", x: 0.55, y: 1.75, w: 6.4, h: 4.2 });
  cap(s, "FDTD 走一步 = 两次旋度 + 两次更新，然后循环", 0.55, 5.98, 6.4);

  s.addText("我复现的四块", T({ x: 7.3, y: 1.8, w: 5.5, h: 0.3, fontSize: 14,
    bold: true, color: NAVY }));
  const mine = [["自己写 Yee FDTD", "先把尺子校准 —— 网络准不准，得有可信的东西去量"],
                ["生成训练数据", "平面波 + 它的旋度，1500 个样本，不用仿真"],
                ["复现 DCO 网络", "两条腿：一条吃场，一条吃坐标；2.25 M 参数"],
                ["三组测试", "单步准不准 / 换网格还能用吗 / 塞回时间推进"]];
  let y = 2.2;
  mine.forEach(([t, d], i) => {
    card(s, 7.3, y, 5.5, 0.92);
    badge(s, i + 1, 7.55, y + 0.3, i === 3 ? TEAL : GREEN, 0.34);
    s.addText(t, T({ x: 8.05, y: y + 0.16, w: 4.6, h: 0.28, fontSize: 14,
      bold: true, color: NAVY }));
    s.addText(d, T({ x: 8.05, y: y + 0.47, w: 4.6, h: 0.28, fontSize: 11,
      color: MUT }));
    y += 1.05;
  });
  s.addText("前三块是「把论文搭起来」，第四块才是「看它到底行不行」—— 问题也出在第四块。",
    T({ x: 7.3, y: 6.35, w: 5.5, h: 0.5, fontSize: 11.5, italic: true,
        color: ORANGE, lineSpacing: 16 }));

  s.addNotes(
    "左边这张图：FDTD 走一步就是两次旋度、两次更新，然后循环几千到几十万次。论文把两个红框换成同一个神经网络。\n" +
    "右边四块是我自己做的，后面四页各讲一块。\n\n" +
    "【追问】为什么叫算子不叫网络？\n" +
    "答：普通网络学「这个输入对这个输出」；算子学「函数到函数」的映射，所以换了网格分辨率同一套权重还能用。"
  );
}

/* ═════════ P10 · 块① 基准 ═════════ */
{
  const s = p.addSlide();
  frame(s, "复现 · 块 ①", "先把尺子校准",
        "网络准不准，取决于拿什么去量它。所以第一件事不是搭网络，是证明我的参考解是对的。");

  s.addImage({ path: F + "B_cavity.png", x: 0.55, y: 1.7, w: 8.55, h: 3.5 });
  cap(s, "50 mm 立方腔，32³ 网格，8192 步 —— 我自己写的 FDTD 现场算出来的频谱",
      0.55, 5.24, 8.55);

  const box = [["解析公式", "教科书闭式解", "理论真值", GREEN],
               ["我写的 FDTD", "自己实现", "-0.10% ~ -0.30%", TEAL],
               ["CST 商业软件", "独立第三方", "-0.11% ~ -0.37%", "6C7A89"]];
  let y = 1.8;
  box.forEach(([t, d, r, col]) => {
    card(s, 9.4, y, 3.4, 1.05);
    s.addText(t, T({ x: 9.65, y: y + 0.12, w: 2.9, h: 0.26, fontSize: 12.5,
      bold: true, color: NAVY }));
    s.addText(d, T({ x: 9.65, y: y + 0.39, w: 2.9, h: 0.24, fontSize: 10.5,
      color: MUT }));
    s.addText(r, T({ x: 9.65, y: y + 0.66, w: 2.9, h: 0.28, fontSize: 12.5,
      bold: true, color: col }));
    y += 1.18;
  });
  s.addText("三个互相独立的来源，\n答到了同一组数",
    T({ x: 9.4, y: 5.4, w: 3.4, h: 0.6, fontSize: 12.5, bold: true,
        color: ORANGE, align: "center", lineSpacing: 18 }));

  strip(s, 5.95, [
    { text: "为什么非要拉 CST 进来：", options: { bold: true, color: ORANGE } },
    { text: "  怕自己的 FDTD 写错了，却和自己生成的训练数据「自洽地错」—— "
          + "那样后面三组测试全过，结论却全是假的。第三方求解器是独立的一票。",
      options: { color: INK } }]);

  s.addNotes(
    "（约 35 秒）\n" +
    "这一块听起来最不起眼，但它是整个复现的地基。\n" +
    "50 毫米立方腔，32³ 网格，跑 8192 步，做 FFT。橙色虚线是解析公式给的谐振频率，青色是我的 FDTD 算出来的谱——五个模全部对上，误差 0.1% 到 0.3%。CST 里独立建同一个腔体，误差 0.11% 到 0.37%。\n" +
    "顺便讲一个复现才发现的坑：论文写的时间步长 3.075 皮秒其实超过了 Courant 稳定限 3.009 皮秒，按它写的跑会炸；还有它说源放在正中心，但正中心是所有偶数模的节点，那样 Table II 里三个模根本激发不出来。我把源挪开一格才全出来。\n\n" +
    "【追问】为什么要 CST 交叉验证？\n" +
    "答：怕自己的 FDTD 写错了，却和自己生成的数据自洽地错——那样所有测试都会过，但结论全是假的。"
  );
}

/* ═════════ P11 · 块② 数据 ═════════ */
{
  const s = p.addSlide();
  frame(s, "复现 · 块 ②", "训练数据：为什么平面波就够",
        "这是这条路线和前两篇最不一样的地方 —— 数据不用仿真、不用天线、几乎免费。");

  s.addImage({ path: F + "C_sample.png", x: 0.55, y: 1.72, w: 7.3, h: 3.35 });
  cap(s, "一个真实的训练样本（现场用 gen_data.py 生成的，不是示意图）",
      0.55, 5.12, 7.3);

  card(s, 8.15, 1.72, 4.67, 3.35);
  s.addText("为什么这么简单的数据就够", T({ x: 8.45, y: 1.9, w: 4.1, h: 0.3,
    fontSize: 13.5, bold: true, color: NAVY }));
  const chain = [["平面波", PALE, NAVY], ["旋度退化成\n乘一个矢量 k", CALLBG, ORANGE],
                 ["把 k 扫一遍\n= 把算子扫遍", "E4F1EA", GREEN]];
  let cy = 2.28;
  chain.forEach(([t, bg, col], i) => {
    s.addShape(p.ShapeType.roundRect, { x: 8.45, y: cy, w: 4.1, h: 0.56,
      rectRadius: 0.05, fill: { color: bg } });
    s.addText(t, T({ x: 8.45, y: cy, w: 4.1, h: 0.56, align: "center",
      valign: "middle", fontSize: 11.5, bold: true, color: col,
      lineSpacing: 14 }));
    if (i < 2) s.addText("↓", T({ x: 8.45, y: cy + 0.57, w: 4.1, h: 0.2,
      align: "center", fontSize: 12, color: "AAB6C2" }));
    cy += 0.78;
  });
  s.addText("k 从 0 扫到 1048（对应 0–50 GHz），就等于把旋度这个算子所有可能的行为都见过一遍了。",
    T({ x: 8.45, y: 4.46, w: 4.1, h: 0.55, fontSize: 11, color: MUT,
        lineSpacing: 15 }));

  strip(s, 5.5, [
    { text: "所以它能直接用到腔体、微带滤波器、超表面单元。", options: { bold: true, color: ORANGE } },
    { text: "  旋度是局部的、只跟场有关；介质是从更新方程的 ε、μ 进来的，不进旋度。"
          + "学旋度 = 学一件跟具体结构无关的事 —— 这是前两篇做不到的。",
      options: { color: INK } }], CALLBG, 0.95);
  s.addText("对比：前两篇学的是「这一类结构的统计规律」，换个结构就要重造数据集（MAE 那篇明码标价 411 小时）。",
    T({ x: 0.55, y: 6.58, w: 12.25, h: 0.3, fontSize: 11.5, italic: true,
        color: ORANGE }));

  s.addNotes(
    "（约 40 秒）\n" +
    "左边是一个真实的训练样本，我刚才现场生成的：左图是电场的一个切片，右图是它的旋度。右边这个「答案」不是仿真出来的，是解析公式直接写出来的。\n" +
    "为什么这么简单的数据就够？右边这条链：对平面波，旋度这个运算会退化成「乘一个矢量 k」。所以只要把 k 从 0 扫到 1048，就等于把旋度这个算子所有可能的行为见过了一遍。训练集看起来简单得可疑，但对「学旋度」这件事是完备的。\n" +
    "结果就是 1500 个样本，零次电磁仿真，零个天线模型。\n\n" +
    "【追问】这么简单的数据训出来，能用到复杂结构上吗？\n" +
    "答：能。旋度是局部的、只跟场有关，介质是从更新方程的 ε 和 μ 进来的，不进旋度。"
  );
}

/* ═════════ P12 · 块③ 网络 ═════════ */
{
  const s = p.addSlide();
  frame(s, "复现 · 块 ③", "网络：两条腿，一条吃场，一条吃坐标",
        "这个「两条腿」的设计不是装饰 —— 它决定了换网格尺寸能不能不用重训。");

  s.addImage({ path: F + "D_net.png", x: 0.9, y: 1.68, w: 8.1, h: 4.26 });
  cap(s, "DeepONet 的双分支结构：两条腿的输出逐元素相乘，得到旋度",
      0.9, 5.96, 8.1);

  card(s, 9.35, 1.75, 3.47, 1.5);
  s.addText("2.25 M", T({ x: 9.35, y: 1.95, w: 3.47, h: 0.55, align: "center",
    fontSize: 30, bold: true, color: TEAL, fontFace: "Arial" }));
  s.addText("参数 · 3D U-Net 主干", T({ x: 9.35, y: 2.55, w: 3.47, h: 0.28,
    align: "center", fontSize: 11.5, color: MUT }));

  s.addShape(p.ShapeType.roundRect, { x: 9.35, y: 3.42, w: 3.47, h: 2.5,
    rectRadius: 0.05, fill: { color: "FDECEA" } });
  s.addText([
    { text: "我在这里踩的坑\n", options: { bold: true, color: RED, breakLine: true } },
    { text: "论文只说 trunk「吃坐标」，没说吃的是绝对位置还是别的。\n\n",
      options: { color: INK, breakLine: true } },
    { text: "我按字面喂绝对位置 —— 换大网格时网络在外推没见过的数。\n\n",
      options: { color: INK, breakLine: true } },
    { text: "改成只喂格子尺寸后，误差差了 ", options: { color: INK } },
    { text: "17 倍", options: { bold: true, color: RED, fontSize: 15 } },
    { text: "。", options: { color: INK } },
  ], T({ x: 9.62, y: 3.42, w: 2.95, h: 2.5, valign: "middle", fontSize: 11.5,
        lineSpacing: 16 }));

  s.addText("论文没写的实现细节我记录了 8 个 —— 这是最贵的一个，也是读论文发现不了、只有复现才能发现的那种。",
    T({ x: 0.9, y: 6.36, w: 11.9, h: 0.3, fontSize: 11.5, italic: true,
        color: ORANGE }));

  s.addNotes(
    "（约 40 秒）\n" +
    "DeepONet 有两条腿。上面那条叫 branch，吃场本身，主干是 3D U-Net；下面那条叫 trunk，吃「你想在哪里求值」。两条腿的输出逐元素相乘，得到旋度。\n" +
    "关键是下面这条腿：坐标是输入，不是训练时固定死的。所以换网格尺寸只是换一份 trunk 输入，权重不用动——这就是「算子」和普通网络的区别。\n" +
    "右下红框是我踩的坑：论文只说 trunk 吃坐标，没说吃什么坐标。我按字面喂绝对位置，结果 16³ 训练时坐标最大 12 毫米，48³ 推理要到 37.6 毫米，网络在外推没见过的数。改成只喂格子尺寸 dx dy dz 三个常数之后，误差差了 17 倍。\n\n" +
    "【追问】17 倍是论文里写的吗？\n" +
    "答：不是。论文对这两个细节一个字都没写。17 倍是我做消融对比出来的。"
  );
}

/* ═════════ P13 · 块④ 测试 ═════════ */
{
  const s = p.addSlide();
  frame(s, "复现 · 块 ④", "三组测试：过了两关，卡在第三关",
        "前三块是把论文搭起来，这一块才是看它到底行不行。");

  const tests = [
    ["单步准不准", "在论文自己的配置下\n（32³、同样深度）",
     "我们 7.0e-4\n论文 7.7e-4", "同一档", GREEN, "E4F1EA"],
    ["换网格还能用吗", "16³ 训好的权重\n直接拿去更大的网格",
     "能用\n误差涨 2.2 倍", "见右图", ORANGE, CALLBG],
    ["塞回时间推进", "当成 ∇× 反复调用\n一步一步往前推",
     "第 147 步\n彻底发散", "卡在这里", RED, "FDECEA"],
  ];
  let ty = 1.72;
  tests.forEach(([t, how, res, verdict, col, bg], i) => {
    card(s, 0.55, ty, 5.5, 1.26, bg);
    badge(s, i + 1, 0.8, ty + 0.15, col, 0.32);
    s.addText(t, T({ x: 1.25, y: ty + 0.15, w: 2.3, h: 0.3, fontSize: 14,
      bold: true, color: NAVY }));
    s.addText(verdict, T({ x: 3.5, y: ty + 0.15, w: 2.3, h: 0.3,
      align: "right", fontSize: 14, bold: true, color: col }));
    s.addText(how, T({ x: 1.25, y: ty + 0.54, w: 2.3, h: 0.62, fontSize: 10.5,
      color: MUT, lineSpacing: 14 }));
    s.addText(res, T({ x: 3.5, y: ty + 0.54, w: 2.3, h: 0.62, align: "right",
      fontSize: 12, bold: true, color: INK, lineSpacing: 15 }));
    ty += 1.36;
  });

  s.addImage({ path: F + "E_grid.png", x: 6.4, y: 2.0, w: 6.4, h: 2.93 });
  cap(s, "测试② 的原始数据：同一套 16³ 训好的权重，换到更大的网格上",
      6.4, 5.0, 6.4);

  strip(s, 5.88, [
    { text: "一个今天早上才发现的错误：", options: { bold: true, color: RED } },
    { text: "  测试②我一直拿自己的「相对 L2」去和论文的数字比，但论文报的是另一个口径的误差，"
          + "两者在这份数据上差 30–40 倍。脚本已改、正在重测 —— 所以今天这一栏只给我们自己的数，不给和论文的倍数。",
      options: { color: INK } }], TINT, 0.95);

  s.addNotes(
    "（约 50 秒，这是最重要的一页）\n" +
    "三组测试：第一关单步精度过了；第二关换网格能用，误差涨 2.2 倍；第三关塞回时间推进，第 147 步炸了。\n" +
    "第一关要说明口径：论文报误差的公式直接套在旋度场上会被零点炸掉，我试了三种常见算法，只有「平均绝对误差除以最大值」这一种能让论文自己的两张表互相自洽。按那个口径，在论文自己的网格和深度下我们是 7.0e-4，论文 Table I 是 7.7e-4，同一档。\n" +
    "右图是第二关的原始数据：绿色那根是训练用的 16³，右边四根都是没见过的网格，同一套权重直接拿去用。注意最后两根是非立方网格，反而比 48³ 还好。\n" +
    "灰框那条要主动讲：测试②我原来拿自己的相对 L2 去和论文的数字比，今天早上发现两个口径根本不是一回事，差 30 到 40 倍。所以今天只给我们自己的数，等重测。\n\n" +
    "【追问】第一关在谁的数据上测的？\n" +
    "答：我们自己的测试集，不是论文的数据集——所以说「同一档」，不说「更好」。\n" +
    "【追问】那第二关到底差多少？\n" +
    "答：现在不知道，重测完才能说。宁可说不知道，也不给一个可能是错的倍数。"
  );
}

/* ═════════ P14 · 关键发现 ═════════ */
{
  const s = p.addSlide();
  frame(s, "复现 · 关键发现", "闭环为什么会炸 —— 不是因为不够准",
        "「第 147 步」指的是时间步，不是训练轮数。权重早就冻住了，是拿它当 ∇× 反复调用了 147 次。");

  s.addImage({ path: F + "F_rho.png", x: 0.55, y: 1.72, w: 6.05, h: 3.37 });
  cap(s, "16 个模型实测：每步放大得越狠，活得越短", 0.55, 5.14, 6.05);

  s.addImage({ path: F + "G_time.png", x: 6.95, y: 1.72, w: 5.85, h: 3.28 });
  cap(s, "而且它死在固定的「物理时刻」，不是固定的步数", 6.95, 5.14, 5.85);

  s.addShape(p.ShapeType.roundRect, { x: 0.55, y: 5.5, w: 6.05, h: 1.35,
    rectRadius: 0.05, fill: { color: TINT } });
  s.addText([
    { text: "闭环 = 把同一个算子连乘几百次。\n", options: { bold: true, color: NAVY, breakLine: true } },
    { text: "所以关键不是「一次准不准」，是「每次会不会放大一点」。真 FDTD 的放大倍数 ρ 严格等于 1，"
          + "所以能跑几十万步；我们的网络 ρ = 1.11。",
      options: { color: INK } },
  ], T({ x: 0.85, y: 5.5, w: 5.45, h: 1.35, valign: "middle", fontSize: 12,
        lineSpacing: 17 }));

  s.addShape(p.ShapeType.roundRect, { x: 6.95, y: 5.5, w: 5.85, h: 1.35,
    rectRadius: 0.05, fill: { color: CALLBG } });
  s.addText([
    { text: "所以减小时间步一点用都没有。\n", options: { bold: true, color: ORANGE, breakLine: true } },
    { text: "步数变多了，每步长得少了，撑到的时刻完全不变 —— 这是算子本身的毛病，"
          + "换积分器、缩时间步都改不了。",
      options: { color: INK } },
  ], T({ x: 7.25, y: 5.5, w: 5.25, h: 1.35, valign: "middle", fontSize: 12,
        lineSpacing: 17 }));

  s.addNotes(
    "（约 55 秒）\n" +
    "我一开始以为闭环炸是精度不够，多训练就好。查下去不是。\n" +
    "闭环是把同一个算子连乘几百次，所以关键不是一次准不准，是每次会不会放大一点点。把每步的放大倍数叫 ρ。真 FDTD 的 ρ 严格等于 1，所以它能跑几十万步；我们的网络 ρ 是 1.11。\n" +
    "左图是 16 个模型的实测，ρ 越大活得越短，一条很干净的反比线。\n" +
    "右图更狠：横轴左边是「步数」，同一个模型在不同时间步下散开两倍；右边是「步数乘时间步长」，也就是物理时间——全部塌成一条线。意思是它死在固定的物理时刻，减小时间步只是让你多走几步到达同一个时刻，一点用都没有。\n" +
    "还有一条反直觉的：同一份数据同一个循环，我只换了网络最后一层的输出方式，准一倍的那个反而早死四成。把 ρ 固定住之后，精度对寿命就再也没有解释力了。\n\n" +
    "【追问】ρ 是什么？\n" +
    "答：把一整个时间步写成一个线性映射，取它最大特征值的模长。CFL 条件其实就是「保证 ρ 不大于 1」，所以这不是新东西，是 CFL 背后那个真正的判据。\n" +
    "【追问】论文为什么能跑出它的 Fig.7/8？\n" +
    "答：论文展示了它能跑，但没做稳定性分析——没给 ρ，也没说超过展示的步数会怎样。在有限步数窗口里，「还没发散」和「稳定」长得一模一样。"
  );
}

/* ═════════ P15 · 切入点 ═════════ */
{
  const s = p.addSlide();
  frame(s, "复现 · 我的切入点", "让 ρ = 1 成为结构上的保证，而不是训练碰运气",
        "既然 ρ 是判据，就不该指望它靠训练碰巧落在 1 附近。");

  strip(s, 1.7, [
    { text: "做法一句话：", options: { bold: true, color: NAVY } },
    { text: "  别让网络直接输出旋度。让它输出一个「对称」的滤波器，再和精确的离散旋度复合 —— "
          + "这样复合出来的算子 ρ 恒等于 1，是可以证明的，不是训出来的。",
      options: { color: INK } }], TINT, 0.82);

  s.addImage({ path: F + "H_struct.png", x: 0.7, y: 2.72, w: 9.0, h: 3.5 });
  cap(s, "二维验证（8 个参数）：既比 Yee 格式准，又严格稳定", 0.7, 6.28, 9.0);

  card(s, 9.95, 2.72, 2.87, 3.5);
  s.addText("三维也成立", T({ x: 10.2, y: 2.92, w: 2.4, h: 0.3, fontSize: 13,
    bold: true, color: NAVY }));
  s.addText("12", T({ x: 10.2, y: 3.3, w: 2.4, h: 0.5, fontSize: 30,
    bold: true, color: TEAL, fontFace: "Arial" }));
  s.addText("个参数", T({ x: 10.2, y: 3.82, w: 2.4, h: 0.26, fontSize: 11,
    color: MUT }));
  const d3 = [["误差", "比 Yee 好 4.2 倍"], ["稳定性", "ρ = 1.0000000000"]];
  let dy = 4.28;
  d3.forEach(([k, v]) => {
    s.addText(k, T({ x: 10.2, y: dy, w: 2.4, h: 0.24, fontSize: 10.5,
      color: MUT }));
    s.addText(v, T({ x: 10.2, y: dy + 0.24, w: 2.4, h: 0.28, fontSize: 12,
      bold: true, color: GREEN }));
    dy += 0.68;
  });
  s.addText("但只在均匀自由空间成立\n有介质界面还没做通",
    T({ x: 10.2, y: 5.72, w: 2.4, h: 0.5, fontSize: 10.5, italic: true,
        color: RED, lineSpacing: 14 }));

  s.addText([
    { text: "下一步 ①", options: { bold: true, color: ORANGE } },
    { text: " 把论文 Algorithm 1 的双内层循环补完，测它的 ρ　　", options: { color: INK } },
    { text: "②", options: { bold: true, color: ORANGE } },
    { text: " 把这个结构约束加进 U-Net，才能去做真正需要大网络的场合：非均匀介质、材料界面",
      options: { color: INK } },
  ], T({ x: 0.55, y: 6.62, w: 12.25, h: 0.3, fontSize: 11.5,
        lineSpacing: 16 }));

  s.addNotes(
    "（约 45 秒，收尾）\n" +
    "既然 ρ 是判据，那就别靠训练碰运气，直接写进结构：让网络学的不是旋度本身，而是一个对称的滤波器，再和精确的离散旋度复合。两个对称的东西复合还是对称的，对称算子的特征值是实的，ρ 就能锁在 1——这个可以证，不是训出来的。\n" +
    "左图 (a)：同一个任务上，8 个参数比 Yee 格式准 1500 倍，也比一个放开约束的 2.8 万参数 CNN 准 100 倍。\n" +
    "左图 (b)：更重要的是稳定性。自由 CNN 我一路把时间步降到 CFL 0.08，ρ 还是大于 1——减小时间步救不了它。结构化算子在 CFL 0.7 以下 ρ 严格等于 1。\n" +
    "右边是三维，12 个参数，同样成立。最后那行红字是我主动标的：这个构造现在只在均匀自由空间成立，介质一变对称性论证就不一定成立，这是下一步要解决的，不保证能成。\n\n" +
    "【追问】12 个参数比 2.25M 的 U-Net 还好，是不是说明 U-Net 没必要？\n" +
    "答：不能这么说，不是公平对比。均匀自由空间上的精确旋度本来就是一个平移不变的线性卷积核，自由度就那么十几个。这个对比能说明的只有一条：这道示范算例区分不出架构好坏。\n" +
    "【追问】这算不算否定论文？\n" +
    "答：不算。论文立意是对的，结果我也认为是真的。它没回答的是「为什么能稳」，我给出了判据和一个能保证 ρ 等于 1 的构造。"
  );
}

p.writeFile({ fileName: "复现部分.pptx" }).then(f => console.log("wrote", f));
