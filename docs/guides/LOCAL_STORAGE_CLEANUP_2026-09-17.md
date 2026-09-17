# C:\PI-DON 本地存储清理建议

生成时间：2026-09-17

当前盘点结果：

| 类别 | 体积 | 判断 |
|---|---:|---|
| `evidence/` | 45.24 GB | 主体空间占用，包含正式证据、导入副本、权重和临时烟测 |
| `assets/` | 2.44 GB | 数据集和模型资产，建议保留或迁移，不建议直接删 |
| 根目录服务器返回 zip | 1.70 GB | 已导入后的重复压缩包，可清理 |
| `archive/` | 0.25 GB | 小，可暂留 |

## 可以直接清理

这些文件/目录不是科学复算的主要入口；正式复算使用已解压的 `summary.json`、`REPORT.md`、`manifest.json`、`steps.jsonl` 和 `.pt` 权重目录。

| 项目 | 预计释放 |
|---|---:|
| 根目录 `server_*_return.zip` | 1.70 GB |
| `evidence/server_resource_v1/server_*_return.zip` | 7.26 GB |
| `evidence/server_resource_v1/imports/*/*.zip` | 6.29 GB |
| `evidence/paper01_s1/imports/*/*.zip` | 0.77 GB |
| `evidence/_tmp_paper01_ablation_smoke` | 0.41 GB |
| `evidence/_tmp_paper01_contract_smoke` | <0.01 GB |

合计约 `16.45 GB`。

推荐 PowerShell 清理命令：

```powershell
Set-Location C:\PI-DON

# 只删除已导入后的回传压缩包副本，不删除任何 .pt 权重或解压证据目录
Get-ChildItem -LiteralPath C:\PI-DON -File -Filter "server_*_return.zip" -ErrorAction SilentlyContinue | Remove-Item -Force
Get-ChildItem -LiteralPath C:\PI-DON\evidence\server_resource_v1 -File -Filter "server_*_return.zip" -ErrorAction SilentlyContinue | Remove-Item -Force
Get-ChildItem -LiteralPath C:\PI-DON\evidence\server_resource_v1\imports -Recurse -File -Filter "*.zip" -ErrorAction SilentlyContinue | Remove-Item -Force
Get-ChildItem -LiteralPath C:\PI-DON\evidence\paper01_s1\imports -Recurse -File -Filter "*.zip" -ErrorAction SilentlyContinue | Remove-Item -Force

# 只删除本地烟测临时目录
Remove-Item -LiteralPath C:\PI-DON\evidence\_tmp_paper01_ablation_smoke -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath C:\PI-DON\evidence\_tmp_paper01_contract_smoke -Recurse -Force -ErrorAction SilentlyContinue
```

## 可以迁移到服务器备用后删除本地

这些目录包含原始权重、失败现场或大规模导入证据。不要直接删；建议先整体复制到服务器或外部盘，再在本地保留报告、摘要和索引。

| 项目 | 体积 | 用途 | 建议 |
|---|---:|---|---|
| `evidence/server_resource_v1/imports/` | 14.38 GB | 服务器阶段二/诊断回传原始目录 | 迁移到服务器归档后，本地可只保留 review、summary、manifest |
| `evidence/direct_mechanism_v1/runs/` | 8.53 GB | 直接机制 A/B/P/R 旧失败与 checkpoint | 保留一份原始归档；本地可只留关键失败/最终权重 |
| `evidence/direct_mechanism_v1/s1_phase1/` | 0.78 GB | 本地旧 S1 训练数据与证据 | 迁移后本地可保留报告与 summary |
| `evidence/mechanism_1h_v2/` | 2.10 GB | 一小时机制验证，含旧失败现场 | 必须归档；本地可保留报告与 audit |
| `evidence/mechanism_2h_v1/` | 1.47 GB | 二小时机制推进，含失败现场 | 必须归档；本地可保留报告与 audit |
| `evidence/server_resource_v1/dco_value_review_20260916*` | 2.10 GB | DCO价值对比复查副本 | 若 review 已提交，可迁移后删本地大权重副本 |
| `assets/datasets/` | 1.72 GB | 数据集资产 | 服务器已有备份后可本地只留索引 |
| `assets/models/` | 0.71 GB | DCO/CST等模型资产 | 服务器已有备份后可本地只留关键模型 |

服务器归档建议位置：

```powershell
H:\PI-DON_BACKUP\local_evidence_archive_20260917
```

可在本地把目录压缩后迁移，也可以在服务器直接复制。迁移完成后，再删除本地对应大目录。

## 必须保留本地

- `AGENTS.md`、`PLAN.md`、`STATUS.md`
- `project/plan.json`、`project/actions.jsonl`
- `records/LAB_NOTEBOOK.md`、`records/lab_runs.jsonl`
- `src/`、`scripts/`、`tools/`、`tests/`
- 当前仍在推进的服务器 bundle，例如 `server_paper01_theta_full_bundle.zip`
- 近期汇报材料：`docs/guides/`、`evidence/*_review.md`、`汇报素材/`

## 重要说明

1. 删除回传 zip 不等于删除证据；已解压导入目录仍保留原始数值、权重和报告。
2. 删除或迁移 `.pt` 权重目录前，必须确认服务器或外部盘已有备份。
3. 不建议把 `evidence/` 整体清空；它里面混有正式证据、失败现场和复算入口。
