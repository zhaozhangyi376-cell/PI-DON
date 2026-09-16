# 服务器资源首批：本地只读诊断

新参数更新0次；下面是诊断，不是新增科学PASS。S1R数值来自用户原始摘要，服务器权重尚未本地读回。

| S1R网格 | 宏nMAE | relL2 p90 | Eq5 MRE | 逐样本nMAE≤1% | 最差样本占宏误差总和 |
|---|---:|---:|---:|---:|---:|
| 32x32x32 | 0.041503 | 0.044124 | 1.053257 | 1/16 | 52.71% |
| 64x64x64 | 0.114413 | 0.131491 | 1.477370 | 0/16 | 40.67% |
| 64x96x16 | 0.231327 | 0.444001 | 3.327865 | 0/16 | 20.74% |
| 32x64x16 | 0.177718 | 0.371000 | 4.004410 | 0/16 | 20.43% |

| 原在线臂 | 完整步 | Adam(含失败) | 首次当前Q>5%步 | 首次当前nMAE>1%步 | 成本一致 |
|---|---:|---:|---|---|---|
| A-R | 33 | 10228 | None | None | True |
| A-P | 128 | 56680 | {'accepted_steps': 57, 'value': 0.05127230222998123} | {'accepted_steps': 66, 'value': 0.01258007963088182} | True |
| B-R | 128 | 38127 | {'accepted_steps': 58, 'value': 0.058129473007432625} | {'accepted_steps': 66, 'value': 0.01290465060959644} | True |
| B-P | 128 | 44630 | {'accepted_steps': 58, 'value': 0.05868193010127674} | {'accepted_steps': 66, 'value': 0.01211583510959765} | True |
| B-R2 | 128 | 37588 | {'accepted_steps': 58, 'value': 0.05736194244443626} | {'accepted_steps': 66, 'value': 0.013082206702528347} | True |

## 解释和下一步

较弱旋度分量会放大按分量峰值归一化的误差；保留该分量和绝对误差，不能删掉后宣称过门。
完整训练已完成但盲测未过，需要同题比较旧新权重，不能从当前表断言新网络更差。
在线误差曲线来自已保存逐步记录，64/128权重只读复算在JSON中；原场门FAIL保持。
旧字段名mre_eq5_physical的严格零分支经E0/H0缩放，不能未经复核当物理单位Eq5。

## 已发现的接口限制

- S1R supplied summary only; remote hashes/checkpoints/ledger not locally verified.
- Original S1 plan says per-sample <=1%; code uses mean <=1%. Both reported; no old failure promoted.
- S1 checkpoint saver omits the independent shuffle generator state; true flag is not resume certification.
- M2 weak-reference flags use current reference peak, not the registered full-duration reference.
- Original M2 auditor omits Q and weak-component checks in field_gate_pass; negative evidence remains negative.
- M2 runner saves 64 snapshot but does not enforce its field gate before continuing to 128.
