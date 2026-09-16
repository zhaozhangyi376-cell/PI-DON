# 服务器首批启动

将本地 `C:/PI-DON/evidence/server_resource_v1/server_resource_bundle.zip` 传到服务器 `H:/PI-DON/server_resource_bundle.zip`。包内仅本轮新增代码、协议、总计划/状态和只读报告；不含服务器原始模型，不替换服务器actions、records或整份机器plan。

在服务器已激活的pidon311 PowerShell中逐条执行：

```powershell
Set-Location H:\PI-DON
Expand-Archive .\server_resource_bundle.zip .\server_resource_update
python .\server_resource_update\install_server_resource.py
```

安装器先核对包内哈希，备份被替换代码/PLAN/STATUS，跑本轮针对性测试，随后自动登记并用lab_log执行SR-COMPARE和SR-PERF。原有机器任务和服务器账本保留。已登记任务SKIP，不能重复运行重新领预算。

顺序：先三模型同题诊断（不训练），后最多15次临时Adam吞吐测试。单项缺资产/失败保留记录并转下一独立项。首批要求至少50GiB空闲；实际所需远小于20GiB配额。禁止同时启动其他GPU训练做公平测速。

安装需要现有S1R目录包含summary/audit/history/best/last、train_dev_data.npz及四个blind_data数组；旧模型在assets/models。缺项会明确报告，不自动下载/重训替代。

完成后回传这两个小结果目录（预测数组和临时权重可以留在服务器）：

- `H:/PI-DON/evidence/server_resource_v1/phase1_compare/`中的summary.json、REPORT.md、manifest.json。
- `H:/PI-DON/evidence/server_resource_v1/compute_probe/`中的summary.json、REPORT.md、manifest.json。
- 本轮服务器records/lab_runs.jsonl新增行、project/actions.jsonl新增行，以主机和action_id区分本地同号记录。

三个层次分开：安装/测试完成、诊断执行完成、科学门通过。该批没有启动新的25000更新训练，也没有解锁1024/8192。依据结果再冻结一个有针对性的下一批实验。
