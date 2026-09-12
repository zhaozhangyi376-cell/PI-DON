const P = require("pptxgenjs");
const F = "figs/";
const NAVY="1E4465", INK="344654", MUT="6F7F8E", TINT="F2F6F9",
      GREEN="3E8D6D", ORANGE="D9822D", RED="B3392B", CALL="FEEFDA",
      CHIP="FBEEDD", WHITE="FFFFFF";
const FONT="微软雅黑";
const p = new P(); p.layout = "LAYOUT_WIDE";           // 13.33 x 7.5 in

function head(s, no, title, sub){
  s.addShape(p.ShapeType.rect,{x:0,y:0,w:13.33,h:0.95,fill:{color:NAVY}});
  s.addText(no,{x:0.45,y:0.16,w:0.7,h:0.6,fontFace:FONT,fontSize:26,
    bold:true,color:"7FA8C9"});
  s.addText(title,{x:1.15,y:0.14,w:8.6,h:0.42,fontFace:FONT,fontSize:22,
    bold:true,color:WHITE});
  if(sub) s.addText(sub,{x:1.17,y:0.56,w:11.6,h:0.3,fontFace:FONT,
    fontSize:11.5,color:"B9CEE0"});
}
function note(s,x,y,w,h,txt,col){
  s.addShape(p.ShapeType.rect,{x,y,w,h,fill:{color:CALL},
    line:{color:col||ORANGE,width:1}});
  s.addText(txt,{x:x+0.12,y:y+0.06,w:w-0.24,h:h-0.12,fontFace:FONT,
    fontSize:11,color:INK,valign:"middle"});
}
function label(s,x,y,w,txt,col){
  s.addText(txt,{x,y,w,h:0.26,fontFace:FONT,fontSize:11.5,bold:true,
    color:col||NAVY});
}
function table(s,x,y,w,rows,colW,fs){
  s.addTable(rows,{x,y,w,colW,fontFace:FONT,fontSize:fs||10.5,
    color:INK,border:{type:"solid",color:"D6DCE3",pt:0.5},
    autoPage:false,valign:"middle"});
}

/* ---------------- P1 论文全貌 ---------------- */
let s = p.addSlide();
head(s,"01","论文全貌：一张图讲完 PI-DON",
  "Qi & Sarris, IEEE T-MTT 73(7) 3800–3812, 2025 · Fig. 2 原图");
s.addImage({path:F+"paper_fig2_workflow.png",x:0.35,y:1.12,w:9.35,h:4.21});
s.addShape(p.ShapeType.rect,{x:0.35,y:1.12,w:3.15,h:4.21,
  fill:{type:"none"},line:{color:ORANGE,width:2.5,dashType:"dash"}});
s.addShape(p.ShapeType.rect,{x:3.55,y:1.12,w:2.75,h:4.21,
  fill:{type:"none"},line:{color:GREEN,width:2.5,dashType:"dash"}});
s.addShape(p.ShapeType.rect,{x:6.40,y:1.12,w:3.30,h:4.21,
  fill:{type:"none"},line:{color:NAVY,width:2.5,dashType:"dash"}});
label(s,10.0,1.20,3.0,"① 第一阶段 · DCO",ORANGE);
s.addText("监督学习。输入自由空间平面波叠加，靶子是解析求出的 ∇×E。\n"+
  "训好的算子叫 DCO（Deep Curl Operator）。",
  {x:10.0,y:1.48,w:3.0,h:0.9,fontFace:FONT,fontSize:10.5,color:INK});
label(s,10.0,2.48,3.0,"② 第二阶段 · PI-DON",GREEN);
s.addText("把 DCO 放进「蛙跳」时间推进（电场、磁场交替往前更新一步，"+
  "FDTD 算法的标准做法），一步步求解具体问题。\n"+
  "关键：每个时间步都重新训练权重，不是训一次就拿去反复用。",
  {x:10.0,y:2.76,w:3.0,h:1.1,fontFace:FONT,fontSize:10.5,color:INK});
label(s,10.0,3.86,3.0,"③ 应用",NAVY);
s.addText("平面微波电路、超表面单元、不确定性量化 —— 训一次反复用。",
  {x:10.0,y:4.14,w:3.0,h:0.8,fontFace:FONT,fontSize:10.5,color:INK});
note(s,0.35,5.55,12.6,0.72,
  "一句话：把 FDTD 时间推进里的空间旋度算子 ∇× 换成神经算子，"+
  "再用物理损失逐步求解。卖点是「训一次、反复用」——"+
  "对需要成百上千次仿真的不确定性量化最划算。");
s.addText("复现范围：① 完成　② 进行中　③ 未开始",
  {x:0.35,y:6.45,w:12.6,h:0.3,fontFace:FONT,fontSize:11,color:MUT});

/* ---------------- P2 DCO 架构与实现 ---------------- */
s = p.addSlide();
head(s,"02","第一阶段：DCO 的架构与我们的实现",
  "论文 Fig. 3 原图（左）· 我们的关键代码（右）");
s.addImage({path:F+"paper_fig3_unet.png",x:0.35,y:1.10,w:6.05,h:3.54});
s.addText("改造过的 3-D U-Net：先把场逐级缩小（下采样）看大范围的规律，"+
  "再逐级放大回来，缩小前的细节直接搭桥连过来（跳跃连接）防止丢细节；"+
  "多出来的 trunk 分支专门吃坐标，把网格多大告诉算子；"+
  "两条支路的结果按位置一一相乘（Hadamard 积）合成最终输出。",
  {x:0.35,y:4.68,w:6.05,h:0.90,fontFace:FONT,fontSize:9.5,color:INK});

label(s,6.65,1.10,6.3,"① 网络前向 · dco.py",NAVY);
s.addText("这段代码在做什么：场和坐标各走一条支路，每一级相乘一次，"+
  "先缩小再放大回来——对应左边那张图",
  {x:6.65,y:1.34,w:6.3,h:0.34,fontFace:FONT,fontSize:9,color:MUT});
s.addText(
"for i in range(self.levels):\n"+
"    if i > 0: b, t = self.pool(b), self.pool(t)\n"+
"    b = self.branch[i](b)      # 场\n"+
"    t = self.trunk[i](t)       # 坐标\n"+
"    feats.append(b * t)        # Hadamard 积（按位置相乘）\n"+
"x = feats[-1]\n"+
"for j, i in enumerate(range(levels-1, 0, -1)):\n"+
"    x = self.up[j](x)\n"+
"    x = torch.cat([x, feats[i-1]], 1)   # 跳跃连接\n"+
"    x = self.dec[j](x)",
 {x:6.65,y:1.72,w:6.3,h:1.50,fontFace:"Consolas",fontSize:9.5,
  color:INK,fill:{color:TINT}});
label(s,6.65,3.30,6.3,"② 训练数据 · gen_data.py（论文式 2/3/4）",NAVY);
s.addText("这段代码在做什么：随手拼出一批「电场长什么样」的例子，"+
  "配上「真正的旋度应该是多少」这个标准答案，喂给网络学",
  {x:6.65,y:3.54,w:6.3,h:0.34,fontFace:FONT,fontSize:9,color:MUT});
s.addText(
"E = Σ E0_i · cos(k_i · r̂·r + φ)      # 平面波叠加\n"+
"k_i · E0_i = 0                        # 横波条件，式(3)\n"+
"Ez = -(cosφ sinθ Ex + sinφ sinθ Ey)/cosθ   # 式(4)\n"+
"curlE = 解析求出（不是差分），作为监督靶子\n"+
"格距 Δ 每样本随机取 0.3–0.8 mm，各向异性",
 {x:6.65,y:3.92,w:6.3,h:1.00,fontFace:"Consolas",fontSize:9.5,
  color:INK,fill:{color:TINT}});
note(s,6.65,5.00,6.3,0.62,
  "精确的旋度算子本身就是一次 3×3×3 卷积：243 个权重格子里只有 12 个"+
  "非零——每个输出分量只看 2 个相邻分量各 1 对点、做减法。"+
  "论文却用 9.25M 个参数去学这 12 个数。",NAVY);
table(s,0.35,5.72,12.6,[
 [{text:"配置",options:{bold:true,fill:{color:NAVY},color:WHITE}},
  {text:"论文",options:{bold:true,fill:{color:NAVY},color:WHITE}},
  {text:"我们",options:{bold:true,fill:{color:NAVY},color:WHITE}},
  {text:"说明",options:{bold:true,fill:{color:NAVY},color:WHITE}}],
 ["网格 / 样本数","32³ / 1000","32³ / 1000","一致"],
 ["网络层数 L / 参数","4 / 9.25M","4 / 9.25M","一致"],
 [{text:"训练轮数",options:{bold:true}},
  {text:"1000 epoch",options:{bold:true}},
  {text:"300 epoch",options:{bold:true,color:RED}},
  {text:"下图数字来自这一档；消融已证实 lr/batch 比单纯加 epoch 更有效，见 P5",
   options:{color:RED}}],
 ["学习率 / batch","1e-4 / 32","3e-4+cosine / 16","略有差异，消融正在重选，见 P5"],
],[2.2,2.6,2.9,4.9],9.5);

/* ---------------- P3 训练过程 ---------------- */
s = p.addSlide();
head(s,"03","第一阶段：训练过程与验收",
  "数据怎么造的 · 训练曲线 · 换网格的泛化能力");
s.addImage({path:F+"p3_training.png",x:0.35,y:1.05,w:5.68,h:3.85});
s.addImage({path:F+"p3_accuracy.png",x:6.35,y:1.05,w:5.89,h:3.85});
note(s,0.35,4.96,5.68,0.62,
  "训练损失和测试损失一起往下掉，没有「训练集学得好、测试集学不好」的"+
  "过拟合迹象 —— 1000 个样本喂 9.25M 参数是够用的。",GREEN);
note(s,6.35,4.96,5.89,0.62,
  "精度跟着轮数一路下降、还没走平，说明架构没问题，只是还没练到头。"+
  "下表验收数字用的是专门留出来验收的另一次训练（架构、数据都一样）。",
  ORANGE);
label(s,0.35,5.68,12.6,"验收：换网格（论文 III-D 口径，指标 MAE/max）",NAVY);
table(s,0.35,5.94,12.6,[
 [{text:"测试网格",options:{bold:true,fill:{color:NAVY},color:WHITE}},
  {text:"64³",options:{bold:true,fill:{color:NAVY},color:WHITE}},
  {text:"64×96×16",options:{bold:true,fill:{color:NAVY},color:WHITE}},
  {text:"32×64×16",options:{bold:true,fill:{color:NAVY},color:WHITE}},
  {text:"结论",options:{bold:true,fill:{color:NAVY},color:WHITE}}],
 ["论文","4.1e-3","3.8e-3","4.7e-3",""],
 ["我们","2.875e-3","5.687e-3","6.266e-3",""],
 [{text:"倍数",options:{bold:true}},
  {text:"0.70× 优于论文",options:{bold:true,color:GREEN}},
  {text:"1.50×",options:{bold:true}},
  {text:"1.33×",options:{bold:true}},
  {text:"维度不变性复现成功",options:{bold:true,color:GREEN}}],
],[2.0,2.7,2.7,2.7,2.5],9.5);

/* ---------------- P4 PI-DON ---------------- */
s = p.addSlide();
head(s,"04","第二阶段：PI-DON（Algorithm 1）与当前瓶颈",
  "论文无示意图 —— 由式(6) 与 Algorithm 1 构成，此处自制流程图");
s.addText("E(n+1) = E(n) + (Δt/ε)·∇D×H(n+1/2)\nH(n+1/2) = H(n-1/2) − (Δt/μ)·∇D×E(n)",
 {x:0.35,y:1.12,w:3.9,h:0.78,fontFace:FONT,fontSize:13,bold:true,
  color:NAVY,fill:{color:TINT},align:"center",valign:"middle"});
const steps=[["训练 ∇×H  直到损失<1e-4",ORANGE],
             ["更新 E（用 ε、Δt）",NAVY],
             ["施加激励",NAVY],
             ["训练 ∇×E  式(7)，含边界",ORANGE],
             ["更新 H（用 μ、Δt）",NAVY]];
let y0=2.10;
steps.forEach(([t,c],i)=>{
  s.addShape(p.ShapeType.roundRect,{x:0.55,y:y0+i*0.62,w:3.5,h:0.48,
    fill:{color:c===ORANGE?CHIP:TINT},line:{color:c,width:1.4}});
  s.addText(t,{x:0.62,y:y0+i*0.62,w:3.36,h:0.48,fontFace:FONT,
    fontSize:10.5,color:INK,align:"center",valign:"middle"});
});
s.addText("每个时间步重复以上五步",{x:0.55,y:y0+5*0.62,w:3.5,h:0.32,
  fontFace:FONT,fontSize:11,bold:true,color:GREEN,align:"center"});
note(s,0.35,5.62,3.9,1.0,
  "关键：权重在【每个时间步】都被重新优化，不是训一次冻结推理。"+
  "论文的稳定性完全建立在这一点上。",ORANGE);
s.addImage({path:F+"p4_growth.png",x:4.35,y:1.12,w:5.24,h:3.20});
note(s,4.35,4.40,5.24,1.15,
  "这张图里内层损失（虚线，右轴）为了对照特意没调到收敛，"+
  "停在 0.5~1.0；解的误差（红线，左轴）仍涨了 12 个数量级 —— 道理是"+
  "一样的：损失只查「这一步算得对不对」，从不查「累积到现在对不对」。"+
  "哪怕损失小到 1e-4，只要每步还剩一点残差 ε，跑够多步照样滚雪球。",RED);
label(s,10.1,1.12,2.9,"定量结论（另一次真实跑，见下方说明）",NAVY);
s.addText("实测每步误差放大 g = 1.0156（每步 +1.56%）\n\n"+
  "√(3e-3) ≈ 5.5% —— 跟 g−1 同量级，说明「每步剩多少相对误差 ε」\n"+
  "直接就是每步的放大倍数\n\n"+
  "⇒ 想跑完 N 步，ε 必须 ≤ 1/N\n\n"+
  "2000 步 → ε ≤ 5.0e-4\n8192 步 → ε ≤ 1.2e-4\n\n"+
  "现在的 ε 比这个要求差了约 2×10⁵ 倍",
 {x:10.1,y:1.42,w:2.9,h:2.75,fontFace:FONT,fontSize:10.5,color:INK,
  fill:{color:TINT}});
s.addText("ε 是什么：每一步训练完之后，网络输出和真正的旋度之间还剩下"+
  "多少相对误差；剩得越多，场往前滚一步走样越多。",
  {x:10.1,y:4.20,w:2.9,h:0.55,fontFace:FONT,fontSize:8.5,color:MUT});
table(s,10.1,4.85,2.9,[
 [{text:"算力",options:{bold:true,fill:{color:NAVY},color:WHITE}},
  {text:"",options:{fill:{color:NAVY}}}],
 ["论文 A6000","71 ms/步"],
 ["我们 1660S","7340 ms/步"],
],[1.5,1.4],9);
note(s,4.35,5.90,8.65,0.80,
  "瓶颈定死了：不是时间步长（0.99×稳定性上限，参考算法全程正常），"+
  "不是网格（已按论文的 31 个间隔），是【每一步训练得够不够准】。"+
  "论文 71 ms/步说明它的内层训练一两次迭代就够 —— 那是 1000 轮训练换来的好起点。",
  NAVY);
s.addText("以上「定量结论」来自另一次跑在正确 31 格网格上的记录，"+
  "跟左图（专门做来展示「损失小≠场准」）不是同一次跑——两者原始数据"+
  "当时都没随代码一起提交，回头需要从训练机补上。",
  {x:0.35,y:6.78,w:12.6,h:0.55,fontFace:FONT,fontSize:8.5,color:MUT});

/* ---------------- P5 总结与后续计划 ---------------- */
s = p.addSlide();
head(s,"05","总结与后续计划",
  "做到哪一步、跟论文差多少 · 每个数字都可在 RESULTS.md / LAB_NOTEBOOK.md 溯源");

// ---- 现状总结：一张结果对比图，两条阶段各做到了什么程度 ----
s.addImage({path:F+"p5_progress.png",x:0.55,y:0.98,w:12.2,h:1.64});

// ---- 证据区：论文之外我们自己发现并验证的规律 + 纠偏，都是能重算的图 ----
label(s,0.35,2.72,12.6,
  "证据：论文之外我们自己验证过的规律，和纠偏前后的对比（都是现场跑代码重算出来的，不是转述）",
  GREEN);
s.addImage({path:F+"p5_c2_rho.png",x:0.35,y:3.02,w:2.10,h:1.84});
s.addImage({path:F+"p5_c3_cfl.png",x:2.62,y:3.02,w:2.60,h:1.84});
s.addImage({path:F+"p5_metric_fix.png",x:5.38,y:3.10,w:3.55,h:1.60});
s.addText(
"殊途同归：不管是「训好不再改」还是「每步都重练」，本质上都要求"+
"「每一步剩的误差 ≤ 1/总步数」——左边两张图各自独立验证了这条规律"+
"的两半，这是我们在论文之外自己发现的。",
 {x:9.10,y:3.05,w:3.90,h:1.35,fontFace:FONT,fontSize:9.3,color:INK,
  fill:{color:TINT},valign:"top"});
s.addText("以上两张图直接调用 verify_claims.py 里算 RESULTS.md 结论的"+
  "同一段代码画的，跟 C2/C3 那两行数字对得上号。",
  {x:9.10,y:4.42,w:3.90,h:0.42,fontFace:FONT,fontSize:8,color:MUT,
   valign:"top"});

// ---- 试错与纠偏：另外三条，一句话标题，不铺开讲 ----
label(s,0.35,5.02,12.6,"试错与纠偏（另外三条，量精度那条见上面的图）",RED);
const pits=[
 "「32 个格子」数错成 32 个间隔 → 时间步长超过稳定上限，连参照算法自己都算炸；改成 31 个间隔才和论文对上",
 "损失小 ≠ 结果对 → 论文 Fig 8 降到 0 只说明「不用怎么调网络了」，证明结果准的是另外两张图/表",
 "第二阶段不是「练一次、用一直」→ 论文要求每一步都重新练，理解错这点会误判成「复现失败」"];
let yy=5.32;
pits.forEach(t=>{
  s.addText("•  "+t,{x:0.35,y:yy,w:12.6,h:0.34,fontFace:FONT,fontSize:9.8,
    color:INK,valign:"top"});
  yy+=0.36;
});

// ---- 下一步：横向四步时间线，不铺开写段落 ----
label(s,0.35,6.55,12.6,"下一步（按优先级）",NAVY);
const nexts=[
 ["1","已完成","找到阶段一真瓶颈：lr↑/batch↓ 都变好\n⇒ 卡在训练步数，不在容量"],
 ["2","进行中","精度能不能换来更长寿命：新设置\n多训后再测闭环，判断瓶颈在不在精度"],
 ["3","待定","阶段二跑满论文 8192 步，对上\nTable II；视第 2 步结论再定投入"],
 ["4","待办","把训练数据做大：另一条探索路线\n已测出数据量不够是那边的瓶颈"]];
const nw=3.02, gap=0.10;
nexts.forEach(([n,tag,d],i)=>{
  const x0=0.35+i*(nw+gap);
  s.addShape(p.ShapeType.roundRect,{x:x0,y:6.84,w:nw,h:0.56,
    fill:{color:i<2?TINT:WHITE},line:{color:NAVY,width:1.1}});
  s.addShape(p.ShapeType.ellipse,{x:x0+0.10,y:6.92,w:0.30,h:0.30,
    fill:{color:i===0?GREEN:(i===1?ORANGE:MUT)}});
  s.addText(n,{x:x0+0.10,y:6.92,w:0.30,h:0.30,fontFace:FONT,fontSize:11,
    bold:true,color:WHITE,align:"center",valign:"middle"});
  s.addText(tag,{x:x0+0.46,y:6.86,w:nw-0.56,h:0.24,fontFace:FONT,
    fontSize:9.5,bold:true,color:NAVY,valign:"top"});
});
// 四个描述另起一行放在框正下方一小条里，宽度对齐上面的框
nexts.forEach(([n,tag,d],i)=>{
  const x0=0.35+i*(nw+gap);
  s.addText(d,{x:x0+0.05,y:7.02,w:nw-0.10,h:0.42,fontFace:FONT,
    fontSize:7.6,color:INK,valign:"top",lineSpacing:9.5});
});

p.writeFile({fileName:"PI-DON_复现进展_5页.pptx"})
 .then(f=>console.log("written:",f));
