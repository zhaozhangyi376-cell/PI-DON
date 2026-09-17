# PAPER01-S1-THETA-FULL 协议：角度过滤版完整第一阶段诊断

## 问题

`PAPER01-ABLATION-SMOKE` 四臂短预算消融显示 `theta_min_0p5` 是论文式幅值构造中 macro nMAE 最低的变体，最优/baseline macro nMAE 比值为 0.725887。该行动回答：把这一受控角度过滤从 2000 Adam 延长到完整 25000 Adam 后，第一阶段 DCO 是否明显改善。

## 冻结配置

- 数据：`theta_min_0p5`，即保留 Eq.(4) 的 Ex/Ey 抽样后求 Ez，但拒绝 `abs(cos(theta)) < 0.5` 的近奇异角样本。
- 网格：32x32x32。
- 样本：1000，80/20 划分。
- 网络：四级 DCO，fresh 随机初始化，不加载旧权重。
- 优化：Adam，恒定 lr=1e-4，等效 batch=32，microbatch=8。
- 预算：25000 Adam 更新。

## 输出

服务器输出目录：`_01/evidence/paper01_theta_full_v1/`。

必须保存根目录 `summary.json`、`REPORT.md`，以及 `theta_min_0p5/` 下的 manifest、paper_contract、sample_specs、variant_contract_stats、history、summary、REPORT、best.pt、last.pt。

## 成功判据

- 完成 25000 Adam 更新。
- 保存完整证据和 lab_log。
- 本地回传审计列出 best test MSE、macro nMAE、relL2 p90、Eq.(5) MRE、Ez 放大统计和 checkpoint 哈希。

## 判读边界

- 该行动是第一阶段受控过滤诊断，不是论文原始配置复现。
- 结果好只能说明“近奇异角处理值得作为未公开细节候选继续追”；不能直接把 `PAPER01-S1` 改判成功。
- 不解锁第二阶段、1024 或 8192；若要使用该权重进入第二阶段，必须另行登记独立任务和盲测门。
