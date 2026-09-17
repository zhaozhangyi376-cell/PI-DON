# PAPER01-S1：论文显式配置第一阶段参考协议

## 目的

在 `C:/PI-DON/_01` 建立独立第一阶段参考，回答原文明示的坐标trunk、常数学习率和逐分量local-maximum归一化是否改变DCO精度及后续初始化质量。它与当前工程配方并行，不覆盖旧S1/S1R。

## 原文明示配置

- 32x32x32输入；1000样本；80%训练/20%测试；
- 三维双下采样分支U-Net；四级；3x3x3卷积；GELU；残差；2x2x2池化和转置卷积；Hadamard融合与跳连；
- 坐标和E场作为两个三维向量输入；解析curl E为监督目标；
- 网格尺寸各自在0.3至0.8 mm；方向角范围、k范围0至1048 rad/m、Ex/Ey幅度0至5；
- Adam，1000 epoch，常数学习率1e-4，batch 32；
- 输出各分量按local maximum归一化；
- Eq.(5) MRE与Fig.5固定案例单独报告。

## 未公开且必须登记的假设

基础通道数、训练样本波数量、复数场实数表示、坐标单位/原点/Yee偏移、local范围和物理反归一化、训练loss精确归约、随机种子。首次更新前全部写入 `paper_contract.json` 和manifest，不因结果改变。

## 两阶段执行预算

1. GPU预检：最多5个Adam更新，8^3或32^3由命令指定；只检查形状、梯度、显存、学习率恒定和证据写入。预检不计科学成绩。
2. 完整训练：仅预检PASS后启动；1000 epoch、每epoch25个有效batch更新，共25000个Adam更新；microbatch只作梯度累积，等效batch固定32。不得从主线或失败权重恢复。

完整训练不设置结果导向的提前停止。资源中断记INCOMPLETE并保留last、history和现场；恢复只允许同一行动、相同配置、优化器/RNG和剩余预算。

## 输出

`_01/evidence/paper01_s1_<action>/` 下保存manifest、contract副本、data_specs、history.jsonl、best.pt、last.pt、summary.json、audit.json、REPORT.md和Fig.5/测试图。服务器回传后再在主项目登记独立审计；未经审计不更新论文复现结论。
