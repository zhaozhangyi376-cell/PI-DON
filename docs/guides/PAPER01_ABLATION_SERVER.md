# PAPER01-ABLATION-SMOKE 服务器执行说明

用途：在服务器上运行第一阶段短预算消融，判断 `PAPER01-S1` 的失败是否主要来自 Eq.(4) 近奇异角、Ez 幅值放大或幅值构造/归一化口径。该任务只作诊断，不认证论文复现，不解锁第二阶段、1024或8192。

## 1. 拷贝服务器包

把本地文件复制到服务器同名路径：

```text
C:\PI-DON\server_paper01_ablation_bundle.zip
C:\PI-DON\server_paper01_ablation_bundle.sha256
H:\PI-DON\server_paper01_ablation_bundle.zip
H:\PI-DON\server_paper01_ablation_bundle.sha256
```

本地当前包校验：

```text
SHA256 176650C39549646BA554E6CBC757F1A46BBF5393F85D696ECC5B6DCAF691469F
```

复制到服务器后可选核对：

```powershell
Get-FileHash -Algorithm SHA256 H:\PI-DON\server_paper01_ablation_bundle.zip
Get-Content H:\PI-DON\server_paper01_ablation_bundle.sha256
```

## 2. 在服务器执行

在服务器 Anaconda PowerShell 中运行：

```powershell
Set-Location H:\PI-DON
$env:PYTHONUTF8="1"
$PY="C:\Users\ZZY\.conda\envs\pidon311\python.exe"

Remove-Item .\server_paper01_ablation_update -Recurse -Force -ErrorAction SilentlyContinue
Expand-Archive .\server_paper01_ablation_bundle.zip .\server_paper01_ablation_update -Force

& $PY .\server_paper01_ablation_update\install_paper01_ablation.py
& $PY .\server_paper01_ablation_update\server_paper01_ablation_queue.py
```

运行时应看到类似楼式输出：

```text
[variant 1/4 baseline] update 00050/02000 ...
[variant 2/4 theta_min_0p5] update 00050/02000 ...
```

每个变体会打印 `00050/02000`、`00100/02000` 这样的更新进度；四个变体顺序执行。若只看到 `lab_log run` 开头后短时间无输出，先等到数据生成和第一次训练输出，不要立刻中断。

另开一个服务器 PowerShell 可监控GPU：

```powershell
nvidia-smi -l 5
```

四个变体：

| 变体 | 含义 |
|---|---|
| `baseline` | 当前R1合同数据定义 |
| `theta_min_0p5` | 远离Eq.(4)近奇异角 |
| `ez_cap3` | 限制 `max|Ez|/max|Ex,Ey| <= 3` |
| `projected_amp` | 诊断性正交投影幅值，不冒充论文配置 |

## 3. 跑完后回传

服务器脚本正常结束后会生成：

```text
H:\PI-DON\server_paper01_ablation_return.zip
```

把它复制回本地：

```text
C:\PI-DON\server_paper01_ablation_return.zip
```

## 4. 本地导入审计

在本地 PowerShell 运行：

```powershell
Set-Location C:\PI-DON
py -3.11 run.py ingest_paper01_ablation_return .\server_paper01_ablation_return.zip
py -3.11 run.py project_harness check
```

审计输出：

```text
C:\PI-DON\evidence\paper01_s1\paper01_ablation_return_review.md
C:\PI-DON\evidence\paper01_s1\paper01_ablation_return_review.json
```

## 5. 失败时怎么处理

- 如果服务器任务中断，不要删除 `_01\evidence\paper01_ablation_v1`。
- 如果生成了 `server_paper01_ablation_return.zip`，仍然回传并导入；导入结果会标 `INCOMPLETE`。
- 不要重新运行同一个 action 来“补满预算”。需要继续时先登记新的独立任务。
- 任何变体短训好于 baseline 只说明值得进一步登记完整重训，不直接改变 `PAPER01-S1` 的科学FAIL。
