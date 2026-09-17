# 服务器第二批记录器修复补充

目的：修复 `server_short_tol_probe.py` 中 `RunRecorder(mode="existing")` 的实现错误。`RunRecorder` 只支持 `new` 和 `resume`；原 `SR-SHORT` 行动在创建记录器前失败，已登记为 INCOMPLETE，且 `short_tol_probe` 失败现场必须保留。

后继任务：新增 `SR-SHORT-R1`，仍执行同一科学问题和同一预算语义，但输出到 `evidence/server_resource_v1/short_tol_probe_r1`。不覆盖 `short_tol_probe`，不恢复旧 action，不启动 1024/8192。

数值配置：沿用 `docs/plans/2026-09-15-server-batch2-protocol.md` 的 `TOL1E5-P` 配置。

状态解释：

- 原 `SR-SHORT`：INCOMPLETE，原因是记录器API错误，非科学失败。
- 新 `SR-SHORT-R1`：代码修复后的独立交付行动；真实Adam更新从此行动的 lab_log 记录计数。
- 若 `SR-SHORT-R1` 失败，保留失败现场；不再自动扩大参数搜索。

