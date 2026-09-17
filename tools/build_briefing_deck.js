const fs = require('fs');
const path = require('path');
const pptxgen = require('pptxgenjs');
const sizeOf = require('image-size');

const ROOT = path.resolve(__dirname, '..');
const MATERIAL = path.join(ROOT, '汇报素材');
const OUT = path.join(MATERIAL, 'PI-DON导师汇报_20260917_r4.pptx');
const pptx = new pptxgen();
pptx.layout = 'LAYOUT_WIDE';
pptx.author = 'PI-DON reproduction team';
pptx.subject = 'PI-DON reproduction: electromagnetic theory, DCO operator learning, online adaptation, evidence and next steps';
pptx.title = 'PI-DON 论文复现：从旋度算子到时域闭环';
pptx.company = 'PI-DON';
pptx.lang = 'zh-CN';
pptx.theme = {
  headFontFace: 'Microsoft YaHei', bodyFontFace: 'Microsoft YaHei', lang: 'zh-CN'
};
pptx.defineSlideMaster({
  title: 'MASTER',
  background: { color: 'F7F9FC' },
  objects: [
    { rect: { x: 0, y: 0, w: 13.333, h: 0.08, fill: { color: '1E4D6B' }, line: { color: '1E4D6B' } } },
    { text: { text: 'PI-DON reproduction | 2026-09-17', options: { x: 0.45, y: 7.16, w: 4.2, h: 0.18, fontFace: 'Microsoft YaHei', fontSize: 7.5, color: '687684', margin: 0 } } },
    { text: { text: '证据优先：工程交付 ≠ 科学复现', options: { x: 8.7, y: 7.16, w: 4.15, h: 0.18, fontFace: 'Microsoft YaHei', fontSize: 7.5, color: '687684', align: 'right', margin: 0 } } },
  ],
  slideNumber: { x: 12.85, y: 7.16, w: 0.22, h: 0.18, color: '687684', fontSize: 7.5, align: 'right' }
});

const C = {
  navy: '173B55', blue: '2B6F93', cyan: '3AA7A3', green: '2D8A67',
  orange: 'E07A35', red: 'C9504D', gold: 'C9A227', ink: '243746',
  gray: '687684', light: 'E8EEF3', pale: 'F1F5F8', white: 'FFFFFF'
};

function slide(title, kicker = '') {
  const s = pptx.addSlide('MASTER');
  if (kicker) s.addText(kicker, { x: 0.5, y: 0.28, w: 4.0, h: 0.22, fontSize: 9, bold: true, color: C.cyan, charSpacing: 0, margin: 0 });
  s.addText(title, { x: 0.5, y: kicker ? 0.52 : 0.34, w: 12.25, h: 0.42, fontSize: 25, bold: true, color: C.navy, margin: 0, breakLine: false, fit: 'shrink' });
  return s;
}

function footer(s, source) {
  s.addText(`来源：${source}`, { x: 0.5, y: 6.93, w: 12.0, h: 0.16, fontSize: 7, color: '7A8792', italic: true, margin: 0, fit: 'shrink' });
}

function box(s, x, y, w, h, title, body = '', color = C.blue, opts = {}) {
  s.addShape(pptx.ShapeType.roundRect, { x, y, w, h, rectRadius: 0.05, fill: { color: opts.fill || C.white }, line: { color, width: opts.width || 1.3 }, radius: 0.06 });
  s.addShape(pptx.ShapeType.rect, { x, y, w: 0.07, h, fill: { color }, line: { color } });
  s.addText(title, { x: x + 0.18, y: y + 0.12, w: w - 0.3, h: 0.28, fontSize: opts.titleSize || 15, bold: true, color: opts.titleColor || color, margin: 0, fit: 'shrink' });
  if (body) s.addText(body, { x: x + 0.18, y: y + 0.48, w: w - 0.32, h: h - 0.58, fontSize: opts.bodySize || 11.5, color: C.ink, valign: 'mid', margin: 0.02, breakLine: false, fit: 'shrink', bullet: opts.bullet });
}

function arrow(s, x1, y1, x2, y2, color = C.gray, width = 2) {
  s.addShape(pptx.ShapeType.line, { x: x1, y: y1, w: x2 - x1, h: y2 - y1, line: { color, width, beginArrowType: 'none', endArrowType: 'triangle' } });
}

function pill(s, x, y, w, text, color = C.blue) {
  s.addShape(pptx.ShapeType.roundRect, { x, y, w, h: 0.34, fill: { color }, line: { color }, radius: 0.15 });
  s.addText(text, { x: x + 0.04, y: y + 0.07, w: w - 0.08, h: 0.16, fontSize: 8.5, bold: true, color: C.white, align: 'center', margin: 0, fit: 'shrink' });
}

function imageContain(s, file, x, y, w, h, border = true) {
  if (!fs.existsSync(file)) {
    box(s, x, y, w, h, '图像缺失', path.relative(ROOT, file), C.red);
    return;
  }
  const dim = sizeOf.imageSize(file);
  const r = Math.min(w / dim.width, h / dim.height);
  const iw = dim.width * r, ih = dim.height * r;
  if (border) s.addShape(pptx.ShapeType.rect, { x, y, w, h, fill: { color: C.white, transparency: 0 }, line: { color: 'CCD6DE', width: 0.8 } });
  s.addImage({ path: file, x: x + (w - iw) / 2, y: y + (h - ih) / 2, w: iw, h: ih });
}

function table(s, rows, x, y, w, h, widths, fontSize = 10.5) {
  s.addTable(rows, { x, y, w, h, colW: widths, rowH: 0.42, border: { type: 'solid', color: 'CBD5DD', pt: 0.7 },
    fill: C.white, color: C.ink, fontFace: 'Microsoft YaHei', fontSize, margin: 0.08,
    bold: false, valign: 'middle', autoFit: false,
    bandRow: true, bandColor: 'EFF4F7',
    firstRow: true, firstRowFill: C.navy, firstRowColor: C.white, firstRowBold: true });
}

function flow(s, items, y, colors = []) {
  const left = 0.65, gap = 0.28;
  const w = (12.0 - gap * (items.length - 1)) / items.length;
  items.forEach((item, i) => {
    const x = left + i * (w + gap);
    box(s, x, y, w, 1.0, item[0], item[1], colors[i] || [C.blue, C.cyan, C.green, C.orange][i % 4], { titleSize: 13, bodySize: 9.5 });
    if (i < items.length - 1) arrow(s, x + w + 0.03, y + 0.5, x + w + gap - 0.03, y + 0.5, C.gray, 1.5);
  });
}

function metricCard(s, x, y, w, label, value, note, color) {
  s.addShape(pptx.ShapeType.roundRect, { x, y, w, h: 1.18, fill: { color: C.white }, line: { color, width: 1.5 }, radius: 0.08 });
  s.addText(label, { x: x + 0.16, y: y + 0.12, w: w - 0.32, h: 0.2, fontSize: 10, bold: true, color, margin: 0 });
  s.addText(value, { x: x + 0.16, y: y + 0.38, w: w - 0.32, h: 0.35, fontSize: 22, bold: true, color: C.ink, margin: 0, fit: 'shrink' });
  s.addText(note, { x: x + 0.16, y: y + 0.82, w: w - 0.32, h: 0.22, fontSize: 8.3, color: C.gray, margin: 0, fit: 'shrink' });
}

const img = name => path.join(MATERIAL, name);
const ev = (...parts) => path.join(ROOT, 'evidence', ...parts);

const p128 = JSON.parse(fs.readFileSync(ev('server_resource_v1','imports','server_clean_low_lr128_return_20260916T092721Z','clean_low_lr128','summary.json'), 'utf8'));
const r128 = JSON.parse(fs.readFileSync(ev('server_resource_v1','dco_value_review_20260916_r1','returned','random_low_lr128','summary.json'), 'utf8'));
const op = JSON.parse(fs.readFileSync(ev('briefing_20260917','operator_audit_r1','summary.json'), 'utf8'));

// 1
{
  const s = pptx.addSlide(); s.background = { color: C.navy };
  s.addText('PI-DON 论文复现', { x: 0.7, y: 0.72, w: 8.2, h: 0.7, fontSize: 38, bold: true, color: C.white, margin: 0 });
  s.addText('从“学习旋度算子”到“逐时间步在线适配”的证据链', { x: 0.72, y: 1.55, w: 11.6, h: 0.55, fontSize: 24, color: 'CFE6EF', margin: 0 });
  flow(s, [['阶段一','平面波监督学习 curl'],['固定权重审计','网络是否真的学到算子'],['阶段二','Maxwell 残差在线训练'],['场门验收','与 Yee 参考场比较']], 3.0, ['2B6F93','3AA7A3','2D8A67','E07A35']);
  s.addText('当前结论：算子学习有证据；在线预训练收益未被支持；论文显式参考线已独立建立', { x: 0.72, y: 5.35, w: 11.7, h: 0.45, fontSize: 17, bold: true, color: 'FFD6A3', margin: 0, align: 'center' });
  s.addText('汇报日期：2026-09-17', { x: 0.72, y: 6.55, w: 3.0, h: 0.2, fontSize: 10, color: 'B8CBD5', margin: 0 });
}

// 2
{
  const s = slide('导师真正会追问的三个问题', '汇报导航');
  box(s, 0.7, 1.25, 3.75, 4.65, '1. 电磁上做了什么？', 'DCO 替代的是离散旋度计算，不是直接替代整个 Maxwell 方程；边界、源、时间更新仍需显式处理。', C.blue, { titleSize: 17, bodySize: 15 });
  box(s, 4.78, 1.25, 3.75, 4.65, '2. AI 到底学了什么？', '阶段一学“场 + 坐标 → curl 场”的映射；阶段二每个半步再用物理残差适配网络参数。', C.cyan, { titleSize: 17, bodySize: 15 });
  box(s, 8.86, 1.25, 3.75, 4.65, '3. 结果是否支持方向？', '固定权重 DCO 显著优于随机网络；但在线 128 步预训练没有降低成本，且真实场门失败。', C.orange, { titleSize: 17, bodySize: 15 });
  footer(s, '本项目当前证据总览');
}

// 3
{
  const s = slide('一句话逻辑链：不要把四种“误差”混成一个结论', '逻辑总图');
  flow(s, [['解析平面波','构造 E 与解析 curl'],['阶段一 DCO','监督拟合局部算子'],['阶段二残差','每半步拟合当前 curl'],['Yee 场门','检验递推后的真实场']], 1.25);
  s.addShape(pptx.ShapeType.chevron, { x: 0.9, y: 3.0, w: 11.5, h: 0.65, fill: { color: 'DDEAF0' }, line: { color: 'BCD0DA' } });
  s.addText('训练损失小  →  单步 curl 接近  →  Maxwell 更新接近  →  多步场仍可能累积偏差', { x: 1.2, y: 3.19, w: 10.8, h: 0.24, fontSize: 16, bold: true, color: C.navy, align: 'center', margin: 0 });
  box(s, 1.0, 4.15, 5.25, 1.45, '必要但非充分', '单步残差过门并不保证相位、分量比例和长期递推都正确。', C.orange, { bodySize: 13.5 });
  box(s, 7.05, 4.15, 5.25, 1.45, '验收必须分层', '算子精度、在线残差、六分量场误差、源外探针和长时频谱分别回答不同问题。', C.green, { bodySize: 13.5 });
  footer(s, 'AGENTS.md 科学红线；当前项目验收合同');
}

// 4
{
  const s = slide('复现对象不是一个网络，而是一套两阶段求解机制', '论文方法');
  box(s, 0.7, 1.15, 5.7, 4.9, '阶段一：Deep Curl Operator', '输入：E/H 三分量场 + 对应空间坐标\n输出：curl(E) 或 curl(H) 三分量场\n训练：解析平面波监督\n目的：获得可迁移的旋度算子初始化', C.blue, { bodySize: 14 });
  box(s, 6.95, 1.15, 5.7, 4.9, '阶段二：PI-DON 时间推进', '每个时间半步：\n1) 用 Maxwell 离散目标训练当前 DCO\n2) 达到残差门后更新 E/H\n3) 施加源与边界\n4) 进入下一半步', C.green, { bodySize: 14 });
  arrow(s, 6.42, 3.55, 6.93, 3.55, C.orange, 3);
  pill(s, 6.02, 2.95, 1.3, '权重初始化', C.orange);
  footer(s, 'Qi & Sarris (2025), Sections III-A–III-C, Algorithm 1');
}

// 5
{
  const s = slide('Maxwell 旋度方程决定了时间推进的骨架', '电磁理论');
  s.addText('Faraday 定律', { x: 0.85, y: 1.25, w: 2.2, h: 0.35, fontSize: 17, bold: true, color: C.blue, margin: 0 });
  s.addText('∂H/∂t = − μ⁻¹ ∇×E', { x: 0.9, y: 1.75, w: 4.7, h: 0.58, fontSize: 26, bold: true, color: C.ink, margin: 0 });
  s.addText('Ampère–Maxwell 定律', { x: 6.85, y: 1.25, w: 3.3, h: 0.35, fontSize: 17, bold: true, color: C.green, margin: 0 });
  s.addText('∂E/∂t = ε⁻¹(∇×H − J)', { x: 6.9, y: 1.75, w: 5.1, h: 0.58, fontSize: 26, bold: true, color: C.ink, margin: 0 });
  flow(s, [['已知 Eⁿ','求 curl(Eⁿ)'],['更新 Hⁿ⁺¹ᐟ²','跨半个时间步'],['求 curl(Hⁿ⁺¹ᐟ²)','作为 E 的驱动'],['更新 Eⁿ⁺¹','叠加源与边界']], 3.25);
  box(s, 1.05, 5.05, 11.1, 1.05, 'DCO 的位置', '它替换上面两个“求 curl”的算子调用；时间离散、材料参数、源和边界仍在求解器中。', C.orange, { bodySize: 14 });
  footer(s, 'Maxwell 时域旋度方程；论文 Algorithm 1');
}

// 6
{
  const s = slide('旋度不是“一个点的值”，而是局部环量密度', '电磁理论');
  imageContain(s, img('cc11fc941c1b81fd237eda5c00a37029.png'), 0.65, 1.1, 5.4, 5.35);
  box(s, 6.55, 1.25, 5.95, 1.35, '(∇×E)x', '∂Ez/∂y − ∂Ey/∂z：围绕 x 法向小面的环量。', C.blue, { bodySize: 14 });
  box(s, 6.55, 2.95, 5.95, 1.35, '(∇×E)y', '∂Ex/∂z − ∂Ez/∂x：围绕 y 法向小面的环量。', C.cyan, { bodySize: 14 });
  box(s, 6.55, 4.65, 5.95, 1.35, '(∇×E)z', '∂Ey/∂x − ∂Ex/∂y：围绕 z 法向小面的环量。', C.green, { bodySize: 14 });
  footer(s, '汇报素材/cc11fc...png；连续旋度定义');
}

// 7
{
  const s = slide('Yee 网格：E 与 H 分量本来就不在同一空间位置', '电磁理论');
  imageContain(s, img('Yee单位网格.png'), 0.75, 1.05, 6.2, 5.55);
  box(s, 7.3, 1.25, 5.1, 1.2, '交错放置', 'Ex、Ey、Ez 位于不同边；Hx、Hy、Hz 位于不同面。', C.blue, { bodySize: 13 });
  box(s, 7.3, 2.8, 5.1, 1.2, '离散旋度', '每个 curl 分量由环绕对应面的四条边场差分得到。', C.cyan, { bodySize: 13 });
  box(s, 7.3, 4.35, 5.1, 1.2, '为什么六分量分别验收', '支撑域、参考峰值和物理作用都不同；全局平均可掩盖某一分量超标。', C.orange, { bodySize: 13 });
  footer(s, '汇报素材/Yee单位网格.png；Yee 1966');
}

// 8
{
  const s = slide('传统 FDTD：旋度差分 + 时间交错更新', '电磁理论');
  imageContain(s, img('时域差分求解公式.png'), 0.65, 1.02, 7.1, 5.65);
  box(s, 8.05, 1.25, 4.55, 1.35, '第一半步', '由 Eⁿ 的空间差分更新 Hⁿ⁺¹ᐟ²。', C.blue, { bodySize: 14 });
  box(s, 8.05, 3.05, 4.55, 1.35, '第二半步', '由 Hⁿ⁺¹ᐟ² 的空间差分更新 Eⁿ⁺¹。', C.green, { bodySize: 14 });
  box(s, 8.05, 4.85, 4.55, 1.35, 'PI-DON 改动', '用神经算子输出替代差分 curl，但不删除上述时间更新。', C.orange, { bodySize: 14 });
  footer(s, '汇报素材/时域差分求解公式.png；项目 src/pidon/fdtd.py');
}

// 9
{
  const s = slide('CFL 条件仍然约束时间步长', '电磁理论');
  imageContain(s, img('CFL极限定义.png'), 0.8, 1.15, 5.4, 4.8);
  box(s, 6.75, 1.25, 5.55, 1.35, '稳定性来源', '电磁波每个时间步不能跨越过多网格；这是显式时间积分的数值稳定条件。', C.blue, { bodySize: 13 });
  box(s, 6.75, 3.0, 5.55, 1.35, 'DCO 不自动消除 CFL', '即使 curl 由网络给出，E/H 仍按显式离散式推进。', C.orange, { bodySize: 13 });
  box(s, 6.75, 4.75, 5.55, 1.15, '当前基线', 'n=31 间隔、50 mm 腔体、dt=3.075 ps；均作为实现合同记录。', C.green, { bodySize: 12.5 });
  footer(s, '汇报素材/CFL极限定义.png；当前 solver 配置');
}

// 10
{
  const s = slide('DCO 的输入输出：场和坐标进去，旋度场出来', 'AI 与物理接口');
  box(s, 0.7, 1.45, 2.5, 1.65, 'Branch 输入', 'E(x,y,z)\n3 × Nx × Ny × Nz', C.blue, { bodySize: 15 });
  box(s, 0.7, 4.0, 2.5, 1.65, 'Trunk 输入', '(x,y,z) 坐标\n3 × Nx × Ny × Nz', C.cyan, { bodySize: 15 });
  box(s, 4.45, 2.35, 3.55, 2.25, '双编码器 + Hadamard', '分别提取“场模式”和“空间位置模式”，逐层相乘后解码。', C.green, { bodySize: 14 });
  box(s, 9.25, 2.35, 3.25, 2.25, '输出', 'curl(E)\n3 × Nx × Ny × Nz', C.orange, { bodySize: 16 });
  arrow(s, 3.2, 2.28, 4.45, 2.95, C.gray, 2.2); arrow(s, 3.2, 4.82, 4.45, 4.0, C.gray, 2.2); arrow(s, 8.0, 3.48, 9.25, 3.48, C.gray, 2.2);
  s.addText('不是选取空间中的一个点训练：每个样本包含整个 32³ 网格上的三分量输入与三分量解析 curl 目标。', { x: 1.2, y: 6.15, w: 10.9, h: 0.4, fontSize: 15, bold: true, color: C.navy, align: 'center', margin: 0 });
  footer(s, '论文 Section III-A；_01/src/paper01/model.py');
}

// 11
{
  const s = slide('为什么叫 Deep Operator Network，而不只是 CNN', 'AI 工作原理');
  box(s, 0.8, 1.2, 3.65, 1.55, 'Branch：函数值', '接收某个离散电磁场样本，编码“场长什么样”。', C.blue, { bodySize: 13.5 });
  box(s, 0.8, 4.0, 3.65, 1.55, 'Trunk：查询位置', '接收对应空间坐标，编码“在哪里求算子输出”。', C.cyan, { bodySize: 13.5 });
  box(s, 5.2, 2.25, 2.8, 2.2, '逐层相乘', 'Branch ⊙ Trunk\n场特征 × 位置特征', C.green, { bodySize: 14 });
  box(s, 8.85, 2.25, 3.65, 2.2, '解码为函数', '对整个网格同时输出三分量旋度场。', C.orange, { bodySize: 14 });
  arrow(s, 4.45, 1.98, 5.2, 2.95); arrow(s, 4.45, 4.78, 5.2, 3.72); arrow(s, 8.0, 3.35, 8.85, 3.35);
  box(s, 2.15, 5.85, 9.0, 0.7, '可换网格的前提', '卷积核不依赖固定网格点数，但坐标范围、物理尺度与训练分布仍会影响泛化。', C.red, { titleSize: 12, bodySize: 10.5 });
  footer(s, '论文 Section III-A；DeepONet 概念在本项目中的具体实现');
}

// 12
{
  const s = slide('四层 DCO：每一层的张量如何变化', '网络内部');
  const xs = [0.65, 3.05, 5.45, 7.85]; const ch = ['32','64','128','256']; const sz = ['32³','16³','8³','4³'];
  xs.forEach((x,i)=>{ box(s,x,1.35,1.75,1.45,`Level ${i+1}`,`${ch[i]} 通道\n${sz[i]}`, [C.blue,C.cyan,C.green,C.orange][i], {bodySize:13}); if(i<3) arrow(s,x+1.75,2.05,x+2.38,2.05); });
  box(s, 10.25, 1.35, 2.3, 1.45, '融合底部', 'Branch ⊙ Trunk\n256 × 4³', C.red, { bodySize: 13 });
  arrow(s, 9.6, 2.05, 10.25, 2.05);
  const ux = [10.25,7.85,5.45,3.05,0.65]; const lab = ['256×4³','128×8³','64×16³','32×32³','3×32³'];
  ux.forEach((x,i)=>{ s.addShape(pptx.ShapeType.roundRect,{x,y:4.05,w:1.75,h:1.0,fill:{color:i===4?'FFE8D6':'EAF3F5'},line:{color:i===4?C.orange:C.cyan,width:1.2},radius:0.06}); s.addText(lab[i],{x:x+0.08,y:4.36,w:1.58,h:0.2,fontSize:11,bold:true,color:C.ink,align:'center',margin:0,fit:'shrink'}); if(i<4) arrow(s,x-0.1,4.55,x-0.6,4.55,C.gray,1.5); });
  s.addText('下采样提取大尺度模式；上采样恢复空间分辨率；同层 skip 保留局部细节。', { x: 1.0, y: 5.65, w: 11.3, h: 0.38, fontSize: 15, bold: true, color: C.navy, align: 'center', margin: 0 });
  footer(s, '论文 Section III-A；src/pidon/dco.py；_01/src/paper01/model.py');
}

// 13
{
  const s = slide('逐层输入输出清单：导师可以按张量检查', '网络内部');
  table(s, [
    ['位置','输入','处理','输出'],
    ['Branch L1','E: 3×32³','2×Conv3D + GELU + residual','32×32³'],
    ['Trunk L1','坐标: 3×32³','同构独立编码器','32×32³'],
    ['L2–L4','上一层 + MaxPool 2³','通道翻倍、尺寸减半','64×16³ → 256×4³'],
    ['融合','Branch_i, Trunk_i','Hadamard 逐元素乘','每层融合特征'],
    ['Decoder','底部融合 + skip','转置卷积 + residual block','32×32³'],
    ['Head','32×32³','1×1×1 Conv','curl: 3×32³'],
  ], 0.65, 1.15, 12.0, 4.8, [1.7,2.5,4.2,2.7], 11.5);
  box(s, 1.15, 6.0, 11.0, 0.65, '关键点', '三输出通道分别对应 curl_x、curl_y、curl_z，不是 x/y/z 坐标本身。', C.orange, { titleSize: 11, bodySize: 10.5 });
  footer(s, '网络源码与论文架构文字逐项对照');
}

// 14
{
  const s = slide('阶段一训练数据：不是测量数据，而是可解析平面波', '阶段一');
  imageContain(s, img('平面波输入.webp'), 0.65, 2.45, 5.8, 4.15);
  flow(s, [['采样方向','θ∈[0,π], φ∈[-π,π]'],['采样波数','k∈[0,1048] rad/m'],['采样幅度','Ex,Ey∈[0,5]'],['解析生成','E 与 curl(E)']], 1.25);
  box(s, 6.85, 3.0, 5.55, 1.35, '每个样本', '整个 32³ 网格 × 3 个场分量；不是只取一个空间点。', C.blue, { bodySize: 14 });
  box(s, 6.85, 4.75, 5.55, 1.35, '为什么用平面波', '其旋度可由 k×E₀ 解析得到，监督标签无 FDTD 离散误差。', C.green, { bodySize: 14 });
  footer(s, '论文 Section III-C；汇报素材/平面波输入.webp');
}

// 15
{
  const s = slide('平面波约束：振幅必须与传播方向正交', '阶段一');
  s.addText('E(r) = Σ E₀,m cos(km·r)', { x: 0.9, y: 1.25, w: 5.5, h: 0.5, fontSize: 26, bold: true, color: C.navy, margin: 0 });
  s.addText('km · E₀,m = 0', { x: 7.1, y: 1.25, w: 4.2, h: 0.5, fontSize: 26, bold: true, color: C.green, margin: 0 });
  box(s, 0.8, 2.25, 3.55, 2.75, '采样 1', '先采样 θ、φ 得到单位传播方向 k̂。', C.blue, { bodySize: 15 });
  box(s, 4.9, 2.25, 3.55, 2.75, '采样 2', '采样 Ex、Ey 幅值，再由横向条件确定第三分量。', C.cyan, { bodySize: 15 });
  box(s, 9.0, 2.25, 3.55, 2.75, '物理意义', '无源均匀介质中的平面电磁波为横波。', C.green, { bodySize: 15 });
  arrow(s,4.35,3.62,4.9,3.62); arrow(s,8.45,3.62,9.0,3.62);
  box(s, 1.25, 5.35, 10.8, 0.95, 'Eq.(4) 的数值处理', 'Ez = -(kxEx + kyEy)/kz。kz接近0时会奇异；_01拒绝|cosθ|<0.15。论文没有交代这一步，所以它必须标为 ASSUMED。', C.orange, { titleSize: 12, bodySize: 10.5 });
  footer(s, '论文 Eq.(2) 与 Section III-C；_01/paper_contract.json');
}

// 16
{
  const s = slide('解析标签怎么得到：对平面波直接求导', '阶段一');
  s.addText('∇×[E₀ cos(k·r)] = −(k×E₀) sin(k·r)', { x: 1.05, y: 1.3, w: 11.2, h: 0.65, fontSize: 28, bold: true, color: C.navy, align: 'center', margin: 0 });
  flow(s, [['输入参数','k、E₀、网格坐标 r'],['相位','φ = k·r'],['叉乘幅值','k × E₀'],['解析 curl','−(k×E₀) sinφ']], 2.35);
  box(s, 0.95, 4.25, 5.35, 1.45, '训练比较对象', '网络输出的三个 curl 分量 vs 上式在每个网格位置的解析值。', C.blue, { bodySize: 14 });
  box(s, 7.0, 4.25, 5.35, 1.45, '边界是否参与阶段一', '没有：平面波算子数据不包含腔体 PEC；边界在阶段二求解问题中处理。', C.orange, { bodySize: 14 });
  footer(s, '解析向量微积分；scripts/experiments/phase1_full_run.py；_01/data.py');
}

// 17
{
  const s = slide('一个阶段一样本，从输入到标签的完整形状', '阶段一');
  box(s, 0.7, 1.15, 2.7, 1.55, '参数记录', 'd=(dx,dy,dz)\nθ, φ, 20个k*\nEx/Ey抽样，Eq.(4)求Ez', C.blue, { bodySize: 12.2 });
  box(s, 0.7, 4.15, 2.7, 1.55, '坐标网格', 'x,y,z 位置坐标\n3 × 32 × 32 × 32\n数值单位mm*', C.cyan, { bodySize: 12.2 });
  box(s, 4.4, 1.15, 3.2, 1.55, 'Branch 张量', 'E=(Ex,Ey,Ez)\n3 × 32³', C.green, { bodySize: 14 });
  box(s, 4.4, 4.15, 3.2, 1.55, 'Trunk 张量', '位置坐标\n3 × 32³', C.green, { bodySize: 14 });
  box(s, 9.0, 2.65, 3.3, 1.75, '监督标签', 'curl(E)\n3 × 32³\n每分量局部归一化', C.orange, { bodySize: 14 });
  arrow(s,3.4,1.92,4.4,1.92); arrow(s,3.4,4.92,4.4,4.92); arrow(s,7.6,1.92,9.0,3.25); arrow(s,7.6,4.92,9.0,3.8);
  footer(s, '* 20个波、坐标数值单位和同位采样均为_01冻结假设；论文未公开');
}

// 18
{
  const s = slide('论文、既有主线与 `_01`：哪些相同，哪些只是工程替代', '关键对比');
  table(s, [
    ['项目','论文文字','既有 S1R 主线','独立 `_01`','当前判断'],
    ['网格/样本','32³ / 1000','32³ / 1000','32³ / 1000','一致'],
    ['层数','4','4','4','一致'],
    ['Adam / batch','Adam / 32','Adam / 有效32','Adam / 有效32','一致'],
    ['学习率','1e-4','1e-4→2e-6 cosine','固定1e-4','S1R非原文显式'],
    ['Trunk','空间坐标','网格间距常数通道','位置坐标；mm为ASSUMED','输入类型对齐，单位未知'],
    ['输出归一化','各分量local max','输入RMS导出尺度','目标逐样本逐分量max','_01更字面'],
    ['通道数','未给','base=32','base=32 ASSUMED','无法证明一致'],
    ['幅值与奇异角','Ex/Ey抽样；Eq.(4)','Eq.(4)+角度剔除','Eq.(4)+|cosθ|≥0.15 ASSUMED','剔除规则未公开'],
    ['实/复数与相位','未给','实余弦、零相位','实余弦、零相位 ASSUMED','必须假设'],
  ], 0.45, 1.05, 12.45, 5.55, [1.6,2.5,2.5,2.4,2.8], 9.4);
  footer(s, 'docs/paper/paper_text.txt；phase1_full_run.py；_01/paper_contract.json');
}

// 19
{
  const s = slide('现在回头看：这些偏离理由还合理吗？', '方法审视');
  table(s, [
    ['偏离','当时理由','现在评价','处理'],
    ['Cosine降学习率','提高后期稳定性','工程合理，但不能叫原文配置','_01固定1e-4'],
    ['间距常数作Trunk','直接告诉网络尺度','可能利于缩放，但丢失绝对位置','_01改位置坐标'],
    ['输入RMS归一化','可逆，在线时不需真值尺度','工程必要性强，但与原文字面不同','两条线分开报告'],
    ['硬PEC状态投影','严格满足导体边界','物理合理，但梯度路径不等价','做损失前投影对照'],
    ['严格R<1e-5','控制长期误差','比论文9.6e-3严很多，速度不可横比','论文阈值另线诊断'],
  ], 0.55, 1.15, 12.2, 4.85, [2.0,3.0,3.8,3.1], 10.5);
  box(s, 1.0, 6.05, 11.3, 0.65, '结论', '这些选择大多是“可辩护的工程选择”，但不能继续混称为“作者配置”；因此建立 `_01` 独立参考线。', C.orange, { titleSize: 11, bodySize: 10.5 });
  footer(s, '_01/paper_contract.json；PEC run #301；现有 S1R 配置');
}

// 20
{
  const s = slide('归一化为什么会改变问题本身', '指标与训练');
  box(s, 0.75, 1.25, 3.55, 3.9, '论文文字', '“U-net output was normalized by the local maximum for each component.”\n\n字面理解需要目标 curl 的局部最大值。', C.blue, { bodySize: 14 });
  box(s, 4.9, 1.25, 3.55, 3.9, '主线实现', '用输入场 RMS 和网格尺度构造可逆尺度。\n\n优点：在线推理不需要知道答案。', C.green, { bodySize: 14 });
  box(s, 9.05, 1.25, 3.55, 3.9, '`_01` 参考', '训练/测试阶段按目标每样本、每分量最大值归一化。\n\n优点：更贴原文字面；缺点：在线去归一化仍不明确。', C.orange, { bodySize: 14 });
  s.addText('这是复现中的核心未知项，而不是一句“归一化不同”可以带过。', { x: 1.25, y: 5.75, w: 10.8, h: 0.42, fontSize: 17, bold: true, color: C.red, align: 'center', margin: 0 });
  footer(s, '论文 Section III-C；src/pidon/dco.py；_01/model.py');
}

// 21
{
  const s = slide('四个常见指标回答的是四个不同问题', '指标');
  box(s, 0.65, 1.2, 2.85, 4.9, 'MSE', '训练目标：逐点平方误差平均。\n\n对大误差敏感；受归一化方式影响。', C.blue, { bodySize: 13.5 });
  box(s, 3.75, 1.2, 2.85, 4.9, 'Eq.(5) MRE', '逐点 |误差|/|真值|；真值为零时用绝对误差。\n\n极易被近零点放大。', C.cyan, { bodySize: 13.5 });
  box(s, 6.85, 1.2, 2.85, 4.9, 'nMAE', '某分量所有支撑网格点的平均绝对误差 / 该分量参考峰值。\n\n1%门就是 nMAE≤0.01。', C.green, { bodySize: 13.2 });
  box(s, 9.95, 1.2, 2.85, 4.9, 'relL2 / Q', '全域能量范数意义上的相对误差；六分量加权汇总为 Q。\n\n可掩盖局部分量。', C.orange, { bodySize: 13.2 });
  footer(s, 'paper_protocol.py；field acceptance metric contract');
}

// 22
{
  const s = slide('阶段一已有结果：不能再简单写“未复现”', '阶段一证据');
  metricCard(s, 0.7, 1.25, 2.75, '旧 DCO / 重建 Fig.5', `${(op.models.old_lr1e3.metrics_fig5_reconstruction.macro_nmae*100).toFixed(3)}%`, '宏 nMAE；固定权重零更新', C.green);
  metricCard(s, 3.7, 1.25, 2.75, '随机网络 / 同输入', `${(op.models.random_seed_2026091704.metrics_fig5_reconstruction.macro_nmae*100).toFixed(2)}%`, '宏 nMAE；固定随机种子', C.red);
  metricCard(s, 6.7, 1.25, 2.75, 'S1R 开发集', '2.186%', '1000 epoch，best epoch 970', C.blue);
  metricCard(s, 9.7, 1.25, 2.75, 'S1R 盲测 32³', '4.150%', '盲测门失败', C.orange);
  box(s, 0.85, 3.15, 5.55, 2.2, '可以说什么', '至少一个已有 DCO 对声明的解析平面波重建显著优于随机网络，说明学到了非平凡的 curl 映射。', C.green, { bodySize: 14 });
  box(s, 6.95, 3.15, 5.55, 2.2, '不能说什么', 'S1R 的盲测和换网格门没有通过；不能称“完全达到论文泛化水平”。', C.red, { bodySize: 14 });
  footer(s, 'run #300；SR-COMPARE；S1R summary');
}

// 23
{
  const s = slide('固定权重直接看场：旧 DCO 的 curl 预测', '阶段一证据');
  imageContain(s, ev('briefing_20260917','operator_audit_r1','old_lr1e3_fig5_panel.png'), 0.5, 1.0, 12.3, 5.75);
  footer(s, 'run #300；Fig.5 参数重建，振幅为固定种子假设；parameter_updates=0');
}

// 24
{
  const s = slide('同样输入下的随机网络：不是“看起来也差不多”', '阶段一对照');
  imageContain(s, ev('briefing_20260917','operator_audit_r1','random_fig5_panel.png'), 0.5, 1.0, 12.3, 5.75);
  footer(s, 'run #300；固定随机种子；parameter_updates=0');
}

// 25
{
  const s = slide('固定算子实验回答了“DCO有没有学到东西”', '阶段一结论');
  const ratio = op.models.random_seed_2026091704.metrics_fig5_reconstruction.macro_nmae / op.models.old_lr1e3.metrics_fig5_reconstruction.macro_nmae;
  metricCard(s, 0.8, 1.2, 3.5, '解析平面波宏 nMAE', '0.312%', '旧 DCO；零更新', C.green);
  metricCard(s, 4.9, 1.2, 3.5, '随机对照宏 nMAE', '21.332%', '同结构；零更新', C.red);
  metricCard(s, 9.0, 1.2, 3.5, '误差比', `${ratio.toFixed(1)}×`, '随机 / 旧 DCO', C.orange);
  flow(s, [['结论 A','DCO 学到解析 curl'],['结论 B','不是随机网络偶然输出'],['限制 C','仅一组重建+既有盲测'],['限制 D','不能代表在线腔体输入']], 3.25);
  box(s, 1.0, 5.3, 11.25, 0.9, '科学定位', '这是“第一阶段算子有效性”的直接诊断证据；它不能自动证明“第二阶段预训练能省成本”。', C.blue, { titleSize: 12, bodySize: 11.5 });
  footer(s, 'evidence/briefing_20260917/operator_audit_r1/summary.json');
}

// 26
{
  const s = slide('换网格泛化：有亮点，但不是全面达到论文', '阶段一泛化');
  table(s, [
    ['网格','论文 MRE','旧 paper32 nMAE','S1R blind nMAE','判断'],
    ['32³','L4: 7.7e-4','2.791e-3','4.150e-2','指标口径不同'],
    ['64³','4.1e-3','2.875e-3','数据已回传','旧模型较好'],
    ['64×96×16','3.8e-3','5.687e-3','数据已回传','旧模型略差'],
    ['32×64×16','4.7e-3','6.266e-3','数据已回传','旧模型略差'],
  ], 0.65, 1.25, 12.0, 3.3, [2.0,2.2,2.6,2.6,2.5], 11);
  box(s, 0.9, 5.0, 5.5, 1.25, '为什么不能直接比倍数', '论文列 Eq.(5) MRE；旧表部分是 nMAE。名称相近但数学定义不同。', C.orange, { bodySize: 13 });
  box(s, 6.95, 5.0, 5.5, 1.25, '正确表述', '同口径重测证明模型可在新尺寸前向，但“达到论文精度”仍需同数据同指标。', C.green, { bodySize: 13 });
  footer(s, 'SR-COMPARE；论文 Table/Section III-D；旧表仅作历史对照');
}

// 27
{
  const s = slide('阶段二 Algorithm 1：每个时间步都重新适配 DCO', '阶段二');
  imageContain(s, img('Algorithm1.png'), 0.6, 1.0, 7.0, 5.8);
  box(s, 7.95, 1.2, 4.65, 1.25, '预训练初始化 P', 'H/E 网络从阶段一 DCO 权重开始。', C.blue, { bodySize: 13 });
  box(s, 7.95, 2.85, 4.65, 1.25, '随机初始化 R', '同结构 H/E 网络从固定随机权重开始。', C.red, { bodySize: 13 });
  box(s, 7.95, 4.5, 4.65, 1.45, '比较对象是谁', '初始化的是“本时间推进中要反复训练的两个 curl 网络参数”，不是 E/H 场本身。', C.orange, { bodySize: 13 });
  footer(s, '论文 Algorithm 1 截图；当前 Solver._make_net');
}

// 28
{
  const s = slide('一个完整时间步，代码实际做六件事', '阶段二逐步过程');
  flow(s, [['① 训练 H-net','拟合当前 curl(H) 目标'],['② 更新 E','Ampère 离散式'],['③ 加源+PEC','硬源与切向E置零']], 1.25, [C.blue,C.cyan,C.orange]);
  flow(s, [['④ 训练 E-net','拟合当前 curl(E) 目标'],['⑤ 投影 curlE','法向边界面置零'],['⑥ 更新 H','Faraday 离散式']], 3.3, [C.green,C.orange,C.blue]);
  box(s, 1.0, 5.45, 11.25, 0.85, '“无监督”的含义', '网络不读取 Yee 真值场作为训练标签；训练目标由当前 E/H 和 Maxwell 离散关系内部生成。Yee 只在验收时作独立参考。', C.red, { titleSize: 12, bodySize: 11.5 });
  footer(s, 'src/pidon/pidon_solve.py；论文 Algorithm 1');
}

// 29
{
  const s = slide('半步 A：由当前 H 构造训练目标并更新 E', '阶段二逐步过程');
  box(s, 0.7, 1.25, 3.2, 1.35, '当前状态', 'Hⁿ⁺¹ᐟ² 的六个 Yee 支撑数组', C.blue, { bodySize: 13 });
  box(s, 5.0, 1.25, 3.2, 1.35, '物理目标', '离散 curl(H)\n由当前场直接计算', C.cyan, { bodySize: 13 });
  box(s, 9.1, 1.25, 3.2, 1.35, 'H-net 输出', '预测 curl(H)\n优化至残差门', C.green, { bodySize: 13 });
  arrow(s,3.9,1.92,5.0,1.92); arrow(s,8.2,1.92,9.1,1.92);
  s.addText('Eⁿ⁺¹ = Eⁿ + Δt ε⁻¹ [curl(Hⁿ⁺¹ᐟ²) − J]', { x: 1.05, y: 3.15, w: 11.2, h: 0.55, fontSize: 24, bold: true, color: C.navy, align: 'center', margin: 0 });
  flow(s, [['网络输出','不是直接输出E'],['时间更新','材料参数ε与Δt仍显式'],['源项','J或硬源另行施加'],['边界','更新后应用PEC']], 4.25);
  footer(s, 'pidon_solve.py: fit H → update E → source → apply_pec');
}

// 30
{
  const s = slide('半步 B：由更新后的 E 训练另一个网络并更新 H', '阶段二逐步过程');
  box(s, 0.7, 1.25, 3.2, 1.35, '更新后状态', 'Eⁿ⁺¹ 已包含源与 PEC', C.orange, { bodySize: 13 });
  box(s, 5.0, 1.25, 3.2, 1.35, 'E-net', '预测 curl(Eⁿ⁺¹)\n优化至残差门', C.green, { bodySize: 13 });
  box(s, 9.1, 1.25, 3.2, 1.35, '边界投影', 'curl-E 三分量的法向边界面置零', C.cyan, { bodySize: 13 });
  arrow(s,3.9,1.92,5.0,1.92); arrow(s,8.2,1.92,9.1,1.92);
  s.addText('Hⁿ⁺³ᐟ² = Hⁿ⁺¹ᐟ² − Δt μ⁻¹ curl(Eⁿ⁺¹)', { x: 1.05, y: 3.15, w: 11.2, h: 0.55, fontSize: 24, bold: true, color: C.navy, align: 'center', margin: 0 });
  box(s, 1.0, 4.45, 11.25, 1.25, '两个网络为什么都要训练', '一个拟合 H→curl(H)，另一个拟合 E→curl(E)；它们输入分布、单位尺度和时间相位不同，因此当前实现分开维护。', C.blue, { bodySize: 14 });
  footer(s, 'pidon_solve.py: fit E → _insert_prediction(E) → update H');
}

// 31
{
  const s = slide('论文说“边界在 loss 中”，但具体文字其实是先置零再回传', 'PEC 边界');
  imageContain(s, img('PEC边界条件.png'), 0.7, 1.05, 5.4, 5.25);
  box(s, 6.55, 1.2, 5.75, 1.55, '论文原文操作', '将 PEC 上预测的切向分量设为 0，然后计算 Eq.(7) 损失并反向传播。', C.blue, { bodySize: 14 });
  box(s, 6.55, 3.05, 5.75, 1.55, '当前生产操作', '更新 E 后对场做切向硬投影；另对 curl-E 输出的法向边界面做投影。', C.orange, { bodySize: 14 });
  box(s, 6.55, 4.9, 5.75, 1.15, '审计结论', '都严格满足边界，但对象与梯度路径未证明等价。', C.red, { bodySize: 13 });
  footer(s, '论文边界段落；run #301；汇报素材/PEC边界条件.png');
}

// 32
{
  const s = slide('当前 PEC 掩码具体清零哪些自由度', 'PEC 边界');
  imageContain(s, ev('briefing_20260917','pec_audit','pec_tangential_masks.png'), 0.65, 1.05, 7.2, 5.5);
  box(s, 8.15, 1.25, 4.25, 1.2, 'Ex', '在 y、z 法向的四个 PEC 面上为切向分量。', C.blue, { bodySize: 12 });
  box(s, 8.15, 2.85, 4.25, 1.2, 'Ey', '在 x、z 法向的四个 PEC 面上为切向分量。', C.cyan, { bodySize: 12 });
  box(s, 8.15, 4.45, 4.25, 1.2, 'Ez', '在 x、y 法向的四个 PEC 面上为切向分量。', C.green, { bodySize: 12 });
  footer(s, 'run #301；生产 apply_pec 直接调用审计');
}

// 33
{
  const s = slide('投影放在 loss 前还是场更新后，梯度并不相同', 'PEC 边界');
  imageContain(s, ev('briefing_20260917','pec_audit','projection_gradient_support.png'), 0.75, 1.05, 6.2, 5.45);
  box(s, 7.35, 1.25, 4.95, 1.55, 'Loss 前投影', '被掩码自由度梯度为 0；网络不会被这些位置的误差驱动。', C.blue, { bodySize: 13.5 });
  box(s, 7.35, 3.2, 4.95, 1.55, 'Loss 后改场', '训练时仍可能收到边界误差梯度，只是更新状态时强制满足 PEC。', C.orange, { bodySize: 13.5 });
  box(s, 7.35, 5.15, 4.95, 0.9, '下一步', '在同一短轨迹上做计算图对照，不直接改主线旧失败。', C.green, { bodySize: 11.5 });
  footer(s, 'run #301 toy-autograd + production source hash audit');
}

// 34
{
  const s = slide('阶段二所谓“无监督”：不用 Yee 场训练，但仍有物理目标', '训练目标');
  box(s, 0.75, 1.2, 3.5, 3.9, '训练时可见', '当前 E/H 状态\n材料参数 ε、μ\n离散 curl 目标\n源和边界规则', C.green, { bodySize: 15 });
  box(s, 4.9, 1.2, 3.5, 3.9, '训练时不可见', 'Yee-FDTD 参考场\n未来时间步真实场\n最终频谱答案', C.red, { bodySize: 15 });
  box(s, 9.05, 1.2, 3.5, 3.9, '验收时使用', 'Yee 场只用于独立计算 Q、六分量 nMAE、源外探针和波形。', C.blue, { bodySize: 15 });
  s.addText('因此：Yee 参考算出来并不等于 PI-DON “偷看答案”；它相当于测试集标签。', { x: 1.1, y: 5.75, w: 11.1, h: 0.42, fontSize: 16, bold: true, color: C.navy, align: 'center', margin: 0 });
  footer(s, '当前 solver 与 field acceptance audit');
}

// 35
{
  const s = slide('为什么先做 1→4→16→64→128，而不是直接 8192', '实验逻辑');
  flow(s, [['1个半步','目标是否可达'],['4完整步','H/E循环能否闭合'],['16步','短期状态误差'],['64步','首次场门'],['128步','分量累积误差']], 1.25);
  const vals = [['1 E','3769 Adam','DIAGNOSTIC PASS'],['4步','10558 Adam','PASS_MICRO'],['16步','完整通过','PASS_MICRO'],['64步','全场门通过','PASS_64'],['128步','残差全过；场门FAIL','Ex/Ey>1%']];
  table(s, [['阶段','成本/结果','含义'], ...vals], 1.0, 3.0, 11.3, 2.7, [2.0,3.4,5.9], 11);
  footer(s, 'server_resource_v1 分阶段登记证据；不是把 Adam 更新数当成时间步数');
}

// 36
{
  const s = slide('预训练初始化 P：64 步过门，128 步分量门失败', '阶段二结果');
  metricCard(s, 0.75, 1.2, 2.65, '128步残差接受', `${p128.accepted_steps}/128`, '每个 H/E 拟合均达到 R<1e-5', C.green);
  metricCard(s, 3.65, 1.2, 2.65, '总场 Q', `${(p128.field_gate_128.global_weighted_relative_l2*100).toFixed(2)}%`, '全六分量加权 relL2', C.blue);
  metricCard(s, 6.55, 1.2, 2.65, 'Ex nMAE', `${(p128.field_gate_128.components.Ex.reason.match(/[0-9.]+/)[0]*100).toFixed(2)}%`, '严格门 1%', C.red);
  metricCard(s, 9.45, 1.2, 2.65, 'Ey nMAE', `${(p128.field_gate_128.components.Ey.reason.match(/[0-9.]+/)[0]*100).toFixed(2)}%`, '严格门 1%', C.red);
  box(s, 0.95, 3.15, 5.45, 2.2, '为什么 Q 过而分量不过', 'Q 把六个分量的能量加权汇总；能量较强且误差较小的分量会稀释 Ex/Ey 的局部平均误差。', C.orange, { bodySize: 14 });
  box(s, 6.95, 3.15, 5.45, 2.2, 'Ex/Ey 超 1% 能否忽略', '不能在已登记严格门中忽略；它说明横向电场分量已出现系统偏差，继续递推可能放大。', C.red, { bodySize: 14 });
  footer(s, 'clean_low_lr128/summary.json；门槛在实验前登记');
}

// 37
{
  const s = slide('预训练 P vs 随机 R：当前没有证明预训练节省成本', '阶段二对照');
  imageContain(s, ev('server_resource_v1','dco_value_review_20260916_r2','pretraining_comparison.png'), 0.6, 1.0, 7.2, 5.65);
  table(s, [
    ['初始化','Adam更新','耗时','Q@128','Ex/Ey nMAE','科学门'],
    ['P 预训练','261,209','11,074 s','3.081%','1.549% / 1.631%','FAIL'],
    ['R 随机','159,240','6,837 s','3.133%','1.780% / 1.770%','FAIL'],
  ], 8.05, 1.35, 4.7, 2.4, [0.65,0.75,0.7,0.65,1.05,0.65], 7.5);
  box(s, 8.05, 4.15, 4.7, 1.55, '可下结论', '在这一条同规则 128 步轨迹上，P 没有显示成本优势；R 反而更快。', C.red, { bodySize: 12.5 });
  box(s, 8.05, 5.9, 4.7, 0.62, '不可外推', '单一随机种子不能证明预训练永远无用。', C.orange, { titleSize: 10, bodySize: 9.5 });
  footer(s, 'dco_value_review_20260916_r2/REPORT.md');
}

// 38
{
  const s = slide('关键机制：平面波上很准，到了首个腔体 E 输入却严重失配', '分布迁移');
  imageContain(s, ev('briefing_20260917','operator_audit_r1','old_lr1e3_first_e_panel.png'), 0.55, 1.0, 7.1, 5.65);
  metricCard(s, 8.0, 1.25, 4.25, '旧 DCO 首个腔体 E', 'relL2 = 7.12', '固定权重，零更新', C.red);
  metricCard(s, 8.0, 2.85, 4.25, '全局 nMAE', '3.01%', 'z目标严格为0，分量宏nMAE不可定义', C.orange);
  box(s, 8.0, 4.45, 4.25, 1.5, '解释', '硬源产生尖锐、局域、带边界的输入；它与阶段一平滑平面波训练分布完全不同。在线适配是在修复这一迁移。', C.blue, { bodySize: 12.5 });
  footer(s, 'run #300；current cavity first nonzero E; Yee curl target仅作诊断');
}

// 39
{
  const s = slide('所以 DCO 的意义需要拆成三个可证伪命题', '研究判断');
  box(s, 0.7, 1.15, 3.75, 4.9, '命题 A：学到算子', '固定权重在未参与本轮训练的解析平面波上显著优于随机。\n\n当前：有支持。', C.green, { bodySize: 15 });
  box(s, 4.78, 1.15, 3.75, 4.9, '命题 B：省在线成本', '相同轨迹、相同门槛下，预训练应更少更新或更短时间。\n\n当前：未支持。', C.red, { bodySize: 15 });
  box(s, 8.86, 1.15, 3.75, 4.9, '命题 C：可冻结复用', '问题训练完成后冻结网络，应能在后续/相似问题直接推进。\n\n当前：尚未运行。', C.orange, { bodySize: 15 });
  footer(s, 'AGENTS.md 第一条科学红线；当前固定算子与P/R证据');
}

// 40
{
  const s = slide('当前状态：不是“毫无进展”，而是证据把问题定位了', '阶段状态');
  table(s, [
    ['层级','当前结果','状态','能否支持论文主张'],
    ['阶段一旧 DCO 固定算子','平面波宏nMAE 0.312%，远优于随机','支持局部算子学习','部分支持'],
    ['阶段一 S1R 盲测','32³ nMAE 4.15%，换网格门失败','FAIL','不支持完整泛化'],
    ['阶段二残差','P/R 都完成128严格残差步','PASS delivery','只说明可拟合每步目标'],
    ['阶段二真实场','P: Q 3.08%，Ex/Ey >1%','严格 FAIL','不支持128场门'],
    ['预训练收益','P比R多64%更新、慢约62%','FAIL','当前不支持省成本'],
    ['1024/8192','未获严格资格','NOT_RUN','不得启动'],
  ], 0.55, 1.05, 12.2, 5.35, [2.3,4.5,2.0,3.4], 10.2);
  footer(s, 'STATUS.md；run #300/#301；dco_value_review_r2');
}

// 41
{
  const s = slide('独立 `_01`：把“论文明确项”和“我们猜的项”拆开', '下一步');
  flow(s, [['EXPLICIT','32³/1000/4层/Adam/1e-4/batch32/1000epoch'],['DERIVED','Eq.(4)横波约束与解析curl'],['ASSUMED','mm单位/奇异角剔除/20个波/同位采样']], 1.2, [C.green,C.blue,C.orange]);
  box(s, 0.8, 3.0, 3.65, 2.5, '改变 1：Trunk', '从网格间距常数通道改为真实空间位置坐标。', C.blue, { bodySize: 14 });
  box(s, 4.85, 3.0, 3.65, 2.5, '改变 2：学习率', '固定 1e-4，不使用论文未说明的 cosine 调度。', C.green, { bodySize: 14 });
  box(s, 8.9, 3.0, 3.65, 2.5, '改变 3：归一化', '逐样本、逐输出分量 local max，贴近原文字面。', C.orange, { bodySize: 14 });
  box(s, 1.2, 5.85, 10.9, 0.62, '边界', '`_01` 先只做阶段一；PEC 计算图对照另立短实验，避免一次改变多个机制。', C.red, { titleSize: 10.5, bodySize: 9.7 });
  footer(s, '_01/paper_contract.json；R1协议；_01/tests（8 tests PASS）');
}

// 42
{
  const s = slide('R1合同自查：完整训练前纠正两处过强表述', '可追溯纠错');
  box(s, 0.75, 1.2, 5.55, 1.75, '旧写法 1', '把“空间坐标”与“坐标以毫米数值输入”合并列为论文明确。', C.red, { bodySize: 13.5 });
  box(s, 7.0, 1.2, 5.55, 1.75, 'R1改法 1', '论文明确输入空间坐标；米或毫米的数值尺度未公开，因此毫米列为ASSUMED。', C.green, { bodySize: 13.5 });
  arrow(s,6.3,2.05,7.0,2.05);
  box(s, 0.75, 3.35, 5.55, 1.75, '旧写法 2', '用正交投影构造横波。这样虽满足k·E₀=0，却改变了已经抽样的Ex/Ey。', C.red, { bodySize: 13.5 });
  box(s, 7.0, 3.35, 5.55, 1.75, 'R1改法 2', '先保留Ex/Ey∈[0,5]抽样，再按论文Eq.(4)求Ez；奇异角剔除单列ASSUMED。', C.green, { bodySize: 13.5 });
  arrow(s,6.3,4.2,7.0,4.2);
  box(s, 1.2, 5.65, 10.9, 0.72, '证据纪律', '旧预检仍保留；R1另建协议、合同哈希和lab run 303，不把旧证据覆盖成新证据。', C.orange, { titleSize: 11.5, bodySize: 10.5 });
  footer(s, 'docs/plans/2026-09-17-paper01-s1-r1-protocol.md；lab run #303');
}

// 43
{
  const s = slide('服务器完整训练合同：这次能明确回答什么', '下一步执行');
  table(s, [
    ['项目','固定值','证据输出'],
    ['数据','1000个32³解析平面波；Eq.(4)；80/20','sample_specs.json'],
    ['网络','4 levels，base=32(ASSUMED)','manifest.json'],
    ['优化','Adam，固定lr=1e-4，有效batch=32','history.jsonl'],
    ['预算','1000 epoch ≈ 25000参数更新','summary.json'],
    ['检查点','fresh init；不读旧权重','best.pt / last.pt'],
    ['进度','每25更新打印epoch、MSE、显存、ETA','实时日志'],
    ['结论','先做同口径阶段一比较','audit.json / REPORT.md'],
  ], 0.7, 1.1, 11.95, 4.9, [2.2,5.0,4.75], 11);
  box(s, 1.1, 6.1, 11.15, 0.62, '注意', '完整训练完成前，`_01` 只能称“实现与预检完成”，不能提前宣称精度复现。', C.red, { titleSize: 10.5, bodySize: 9.7 });
  footer(s, 'server_paper01_bundle.zip；_01/runner.py');
}

// 44
{
  const s = slide('汇报结论：现在最值得推进的不是更长，而是更可比', '结论');
  box(s, 0.75, 1.15, 3.65, 4.9, '已确认', '1. DCO 可学习非平凡 curl 映射\n2. 严格在线残差能连续128步\n3. 当前PEC实现物理边界准确', C.green, { bodySize: 15 });
  box(s, 4.85, 1.15, 3.65, 4.9, '未确认', '1. 论文训练细节完全一致\n2. 预训练降低在线成本\n3. 128步六分量场门\n4. 1024/8192与频谱', C.red, { bodySize: 15 });
  box(s, 8.95, 1.15, 3.65, 4.9, '下一决策', '先跑 `_01` 阶段一并做固定算子/在线首步配对；再决定是改训练分布、边界计算图，还是停止该方向。', C.orange, { bodySize: 15 });
  footer(s, '本轮所有登记证据与独立参考线');
}

// 45
{
  const s = slide('附录：面对导师的快速回答', 'Q&A');
  table(s, [
    ['问题','一句话回答'],
    ['DCO是不是直接输出时域场？','不是；它输出curl，E/H仍由Maxwell时间更新式推进。'],
    ['第一阶段有没有边界？','没有腔体边界；是解析平面波算子学习。'],
    ['第二阶段为什么还训练？','当前场分布含硬源、边界和递推误差，固定平面波DCO迁移很差。'],
    ['Yee参考是否泄漏？','不进入训练，只用于验收；相当于测试集答案。'],
    ['为什么总Q过而Ex/Ey不过？','全局能量加权会稀释单分量误差，因此保留分量门。'],
    ['为何不直接8192？','128严格场门未过，继续只会扩大成本且无法支持科学结论。'],
    ['DCO还有没有意义？','算子学习有证据；在线成本收益仍需更公平的论文显式配对。'],
  ], 0.55, 1.05, 12.2, 5.75, [3.0,9.2], 11.3);
  footer(s, '逐页讲稿与项目证据索引');
}

pptx.writeFile({ fileName: OUT });
console.log(OUT);
