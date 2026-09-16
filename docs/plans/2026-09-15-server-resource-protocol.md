# 服务器首批实施协议

Goal：最低额外训练成本区分第一阶段指标/分布差异、第二阶段误差积累，实测GV100吞吐。

Architecture：复用原DCO、归一化、S1数据和指标；新增只读审计和独立临时测速入口。输出独立，旧协议不改。

Tech Stack：Python3.11、PyTorch、NumPy、matplotlib；服务器pidon311环境。

## SR-LOCAL：本地先行

文件 `scripts/experiments/server_local_review.py`；输入用户summary原文与direct_mechanism_v1 A-R/A-P/B-R/B-P/B-R2记录。输出`evidence/server_resource_v1/local_review`，0 Adam/closure；最多5臂、每臂64/128两个里程碑权重。

待区分：宏误差是否被弱分量/个别样本影响；成本是否包括失败；64/128权重读回与JSONL是否一致，误差何时越线。保存全部样本、三旋度分量、六电磁分量和探针，不删除离群值。当前参考阈值仅作诊断，不替代原全时长门。成功是完整诊断且公开缺项；缺失保留现场，独立服务器任务继续。

## SR-COMPARE：服务器同题重测

文件 `scripts/experiments/server_phase1_compare.py`；输出`phase1_compare`；0 Adam/closure，CPU4线程，GPU eval batch1。固定三模型：旧dco_paper32、旧dco_lr1e3_300、S1R best。四网格×16例，最多192例前向。各模型必须保留checkpoint实际direct/cellsize/rms配置；不支持或缺元数据则失败，不推测。

使用S1R保存blind_data的E/C/D。首次前向前保存模型/输入/协议/源码哈希，核对history/summary/audit/stage/manifest/best/last及lab run295。检查1000连续epoch、每轮25更新、末计数25000、best开发选模、Adam step计数与checkpoint updates；summary/audit一致性，账本action/exit/输出哈希。缺失/矛盾公开记录。全局RNG不等于独立shuffle generator状态；恢复记UNVERIFIED，已完成25000预算不许追加。

逐样本保存三分量nMAE/MAE/参考峰、Eq5 MRE、global nMAE、global relL2、预测数组，统一四网格表。S1R摘要重测容差rtol=1e-4、atol=1e-7。不一致只记录，不改旧成绩。此集合已暴露，三模型均为诊断复测，不选新科学PASS。无六电磁分量/源探针，标N/A。

单模型缺失/OOM保留失败，转下一模型；缺输入该网格INCOMPLETE；独立SR-PERF继续。

## SR-PERF：吞吐与等效批次

文件 `scripts/experiments/server_compute_probe.py`；输出`compute_probe`。seed2026091507；L4/base32/direct/cellsize/RMS，FP32、Adam lr1e-4、等效batch32，无scheduler/AMP；CPU4线程、interop1。

S1R训练前32例；每配置同一数据/随机初态。microbatch依次4/8/16，每配置2预热+3计时更新，最多15 Adam、0closure。预热计入成本；每次提交后CUDA同步和落盘心跳。异常前尾部若不能证明则UNKNOWN。每配置保存末权重、优化器和失败记录，OOM不减批补预算，不用临时权重作为预训练资产。

每配置首步与microbatch4首步全参数比较，相对L2≤1e-4且最大绝对差≤1e-5为工程数值一致。仅在一致且完整完成配置中，用3次计时中位数最低者推荐；报告显存峰值。未通过不推荐；不由此推断论文加速比或自动改正式训练配置。

## 调度、保存、后继

新增输出总配额20GiB；服务器启动前空闲≥50GiB。输入只保存哈希，源码复制。工具 `tools/server_resource_queue.py` 只新增任务，不覆盖服务器账本。GPU按SR-COMPARE→SR-PERF串行，先harness start，再lab_log→run.py --action，结束只追加报告声明。已登记任务打印SKIP不重试；进程异常保留failure.json。

测试 `tests/test_server_resource.py` 覆盖均值/逐样本门区别、失败成本、队列防重复。首批后SR-DESIGN核对同题差异、分量尺度、迁移间距、场/边界/弱参考合同。先修已证实接口并回归，再独立冻结最多一个S1干预和一个在线P/R干预。下一批上限S1 25000 Adam，在线每臂150000、每半步3000、closure0；配方/新未见测试集/恢复测试未冻结前保持BLOCKED。

旧FAIL/RESOURCE_LIMIT保持；无新合格128不启1024/8192。报告分别列执行状态、科学状态、更新/评估/失败成本、恢复资格；图由本批保存脚本读同一证据生成。
