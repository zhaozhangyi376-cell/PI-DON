# 迁到服务器（Windows Server）

## 三个最容易翻车的地方，先说

1. **远程桌面点 X 断开 → 进程继续跑；点「注销 / Sign out」→ 进程全部被杀。**
   三小时的训练千万别注销。要断就点窗口右上角的 X。
2. **别复制整个文件夹。** 代码 228 KB 走 git，数据 150 MB 在服务器上重新生成，
   只有 `.pt` 检查点必须手动拷。
3. **先确认服务器有 NVIDIA 卡且 torch 认得它。** 没有 CUDA 的话这些训练在 CPU 上
   要跑几天，不如不搬。

---

## 三类文件，处理方式完全不同

| 类别 | 大小 | 怎么办 |
|---|---|---|
| 代码（`.py` / `.bat`） | **228 KB** | git 或下载 ZIP |
| 数据（`*.npz`） | 1500 样本约 150 MB | **在服务器上重新生成**，2 分钟 |
| 检查点（`*.pt`） | 每个约 9 MB | **必须手动拷** —— 已被 gitignore，且不可重新生成 |

`*.pt` 和 `*.npz` 都在 `pidon_mvp\.gitignore` 里，所以 git 只会给你代码。

---

## 步骤

### 1. 先查硬件（30 秒，不合格就别往下走）

服务器上开 PowerShell：

```powershell
nvidia-smi
```

看到 NVIDIA 卡和显存数字就继续；报"不是内部或外部命令"说明没装驱动或没有 N 卡，**到此为止**。

### 2. 取代码

有 git 的话：

```powershell
cd C:\
git clone https://github.com/zhaozhangyi376-cell/HFSS_auto.git
cd C:\HFSS_auto
git checkout claude/neural-operator-paper-study-3n1dv1
```

没有 git 就下 ZIP —— 浏览器打开：

```
https://github.com/zhaozhangyi376-cell/HFSS_auto/archive/refs/heads/claude/neural-operator-paper-study-3n1dv1.zip
```

解压到 `C:\HFSS_auto\`。

### 3. Python 与 torch

```powershell
py -0
```

列出 3.11 就直接用；没有的话去 python.org 装 3.11（安装时勾上 "Add python.exe to PATH"）。

```powershell
py -3.11 -m pip install numpy matplotlib
py -3.11 -m pip install torch --index-url https://download.pytorch.org/whl/cu121
py -3.11 -c "import torch;print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

本机装 torch 时踩过代理断流（下载卡在依赖包上）。服务器若重演，先从镜像装依赖再单独装 torch：

```powershell
py -3.11 -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple filelock typing_extensions sympy networkx jinja2 fsspec setuptools
py -3.11 -m pip install torch --index-url https://download.pytorch.org/whl/cu121 --no-deps --timeout 120 --retries 10
```

### 4. 把检查点拷过去 —— 用远程桌面的驱动器映射

**连接前**在「远程桌面连接」里：`显示选项 → 本地资源 → 详细信息 → 勾选「驱动器」→ 勾上 C:`

连上之后，你本机的 C 盘在服务器上是 `\\tsclient\C`。于是在服务器的 PowerShell 里：

```powershell
copy \\tsclient\C\HFSS_auto\pidon_mvp\*.pt C:\HFSS_auto\pidon_mvp\
```

**最关键的是 `dco_L3d.pt`** —— 所有后续训练都从它热启动，其余是对照组。
**别拷 `*.npz`**（150 MB，走 RDP 很慢，而且两分钟就能重新生成）。

### 5. 数据在服务器上生成

```powershell
cd C:\HFSS_auto\pidon_mvp
py -3.11 gen_data.py --n 16 --samples 1500 --out data_16.npz
py -3.11 gen_data.py --n 16 --samples 1500 --dirs per-wave --seed 11 --out data_16_pw.npz
```

### 6. 确认版本一致

```powershell
py -3.11 check_files.py
```

必须 14 行全 `ok`。

---

## 服务器该跑什么（本机跑不动的）

`run_stage4.bat` / `run_stage5.bat` 是按 6 GB 卡调的。下面两个是给大卡的。

### `run_paper_parity.bat` —— 价值最大

```powershell
.\run_paper_parity.bat 2>&1 | Tee-Object parity.log
```

按论文 III-C **原样**跑：**32³ / 1000 样本 / L=4 / 1000 epoch / batch 32 / lr 1e-4**。
需要约 8–10 GB 显存，6 GB 卡装不下。

**它消掉的是对照表里"配置不同"那一整列。** 到目前为止所有数都是 16³ / 400 epoch / L=3，
和论文比的每一行都得挂注解；跑完就是同配置直接对。

脚本跑两次，因为"论文的配置"有一处歧义：
- **literal** —— 绝对坐标进 trunk、max 归一，论文字面写法
- **fixed** —— 我们的两处修正（cellsize 坐标、rms 归一），维度不变性靠它才成立

**两个都跑才能回答一个真问题：论文 Table I 里 L=4 比 L=3 好 7 倍的优势，在修正之后还在不在？**
在 16³ 上它不在 —— 同样 400 epoch，L=4 在 48³ 退化 16.7×，而 L=3 只有 1.42×。
这条若在 32³ 上重现，就不只是复现，是个能写的发现。

### `run_stage5_big.bat` —— 把 K 拉大

```powershell
.\run_stage5_big.bat 16 4 2>&1 | Tee-Object stage5_big.log
```

rollout 显存随 `K × roll-batch` 线性增长。本机只能 K=8 / batch=1。
**K 就是这个实验的全部意义** —— 它决定 loss 能往前看多远，而它要对付的失效
（每步约 2.9% 的指数放大）只有跨多步才看得见。

---

## 别打断本机正在跑的 stage5

99% GPU 利用率是**满负荷在干活**，不是过载；79°C 离 1660 SUPER 的降频阈值（约 83°C）
还有余量；显存只用了 2.5 / 6.0 GB。热降频只会让它**变慢**，不改变任何一次浮点运算的
结果 —— 权重不会因为卡热而变差。

本机那一跑是明天汇报的兜底，服务器跑的是本机根本跑不动的。两边并行，零风险。
**服务器环境半小时配不好就放弃**，用本机结果汇报，已经够了。
