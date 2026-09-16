# SR-64 回传审计模板

本模板由 `tools/ingest_server_64_return.py` 自动填数生成正式报告 `evidence/server_resource_v1/strict64_return_review.md`。不要手填模板替代脚本审计。

## 结论

- 交付状态：`<status>`
- 科学状态：`<scientific_result>`（64步门；不是128/1024/8192门）
- 接受完整时间步：`<accepted_steps>` / target `64`
- Adam更新：`<new_adam_updates>`
- 64步field gate：`<field_gate_64.pass>`
- 结论边界：
  - 若 `PASS_64`：只能另行登记128步验证，不能启动1024/8192。
  - 若 `FAIL`/`RESOURCE_LIMIT`/`INCOMPLETE`：停止该分支，保留失败现场。

## 旧瓶颈专项检查

- 第57步：`<step57 metrics>`
- 第58步：`<step58 metrics>`
- 第64步：`<step64 metrics>`
- 第66步：`<step66 metrics if present>`
- 首次Q>5%：`<first_q_gt_5pct>`
- 首次分量门失败：`<first_component_gate_fail>`

旧128残差轨迹的关键反例是57-58步Q越过5%、66步有效分量nMAE越过1%。SR-64必须专门检查是否跨过这个区域。

## 最后/停止步半步拟合

- H residual：`<fit_H.residual_ratio>`，updates `<fit_H.n_updates>`
- E residual：`<fit_E.residual_ratio>`，updates `<fit_E.n_updates>`

## 六分量和探针

| 分量 | nMAE | absMAE | weak | gate依据 | relL2 |
|---|---:|---:|---|---|---:|
| Ex | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` |
| Ey | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` |
| Ez | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` |
| Hx | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` |
| Hy | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` |
| Hz | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` |

- 源点Ez：dut=`<...>`，ref=`<...>`
- 源外探针：`<...>`

## 证据

- summary: `<imported strict64_probe/summary.json>`
- steps: `<imported strict64_probe/steps.jsonl>`
- report: `<imported strict64_probe/REPORT.md>`
- manifest: `<imported strict64_probe/manifest.json>`

