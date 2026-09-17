# 机制诊断与旧结论验证器审查

日期：2026-09-17。只提出问题；没有修改生产代码、权重、历史报告或状态。

## 范围与验证

本专题完整阅读以下21份实验源码及 `scripts/analysis/verify_claims.py`，共22份。实际行数、SHA256 和其它模块的覆盖统一保存于本审查目录的版本化 `coverage_*.json`，不以测试运行替代源码阅读。

```text
scripts/experiments/run_fdtd_cavity.py
scripts/experiments/stage2_fixed_state.py
scripts/experiments/stage2_interface_probe.py
scripts/experiments/stage2_shared_interference.py
scripts/experiments/mechanism_decision_init.py
scripts/experiments/mechanism_decision_runner.py
scripts/experiments/mechanism_decision_eval.py
scripts/experiments/mechanism_first_failure.py
scripts/experiments/mechanism_path_check.py
scripts/experiments/h_layout_candidate.py
scripts/experiments/r4_fixed_state.py
scripts/experiments/r4_p4a.py
scripts/experiments/r0_v2_audit.py
scripts/experiments/night_init.py
scripts/experiments/night_diagnostics.py
scripts/experiments/refine_night_storage_estimate.py
scripts/experiments/p5_audit.py
scripts/experiments/p5_ab_audit.py
scripts/experiments/server_phase1_compare.py
scripts/experiments/server_local_review.py
scripts/experiments/server_failure_mechanism_audit.py
```

本专题不认领其它实验文件，它们见主报告及其它专题。

- lab319：`reproduce_diagnostic_logic.py` 的4项反例，0次优化器更新。前向身份算子和共享网络测试使用显式替身，不冒充真实网络性能；任务完整性测试抽取实际源码表达式。
- lab320：`reproduce_legacy_claims.py` 的3项反例，0次优化器更新；模拟子进程输出与临时内存文件，不启动旧科学脚本、不重写 RESULTS。
- 这里反例测试通过，表示已复现有缺陷的行为，不是科学验收通过。

## E01 [P1，诊断解释] 线性叠加测试比较的不是同一组输入

位置：`scripts/experiments/mechanism_decision_eval.py:125-140`，关键是第138行。

`p` 是全部随机平面波叠加的网络输出，`p1+p2` 却只包含前两束。生成器允许4至16束，所以差值也含被漏掉的其它波，不能作为算子的非线性缺陷。

实测：把预测替换为严格线性的恒等算子，保留原采样和诊断流程，12束波得到所谓缺陷 **0.829798**；真正的同输入可加性缺陷为0。现存 `evidence/mechanism_decision_v1/phase1_raw.json` 保存了 **0.787333** 这一字段，因此该旧数值不能用来证明DCO偏离线性有多大。

影响边界：不否定同一报告另行算出的预测误差或旧 FAIL，不证明DCO实际上线性。需要比较 `D(e1+e2)` 与 `D(e1)+D(e2)`，并对一般多项和、幅值齐次性分别测试；新结果另存，旧字段保留。

## E02 [P2，已引用的历史结论] H/E 干扰测试中途换了 H 的拟合目标

位置：`scripts/experiments/stage2_shared_interference.py:28`、`:36-38`。

前两次 H 残差用精确 `ch0`；为了推进 E，程序随后原位用 H 拟合预测 `ph` 覆盖 `ch0`。E 训练后的 H 残差由此改为相对 `ph`，不再是相对同一精确旋度。分子、分母和参考对象都可能改变。

lab319 用不训练的替身执行真实 main 控制流，记录三次 H 测量目标为 `[1,1,2]`，确认目标发生变化。旧 `evidence/stage2_shared_interference.json` 的 **H_degradation_ratio=831.6193966** 已在 `docs/history/PAPER_VS_CURRENT_TABLES.md:71` 被引用，用于论证训练 E 导致 H 退化831.6倍。

影响边界：这一倍数不是同一目标下的严格前后比较，不能据此量化遗忘程度。共享参数可能仍有干扰，但需要固定不可变的 H 输入和精确目标重新测量；本次没有原位重测或判定干扰不存在。此诊断错误不会自动改变独立 E/H 网络已生成的场。

## E03 [P2，完整性] 未完成的固定状态任务集合也可能 PASS

位置：`scripts/experiments/h_layout_candidate.py:224-228`；`scripts/experiments/r4_fixed_state.py:155-156`；`scripts/analysis/verify_claims.py:1058-1064`。

A3 检查总数却在 `all()` 中排除 NOT_RUN，两个任务都 NOT_RUN 仍 True；R4 只要求实际任务非空及逐任务通过，计划要43/96两状态，只有43也 True；旧 verify 的 P3 门只检查失败列表为空，空 tasks 得到 PASS。这三条已分别用实际表达式/函数复现。

影响边界：已保存 A3/R4 开发结果为 False，不因此改判旧失败。漏洞影响缺项输入和未来复用的认证可靠性。建议先验证完整、唯一、匹配登记的任务身份，再检查有限数值和预算；缺项 INCOMPLETE，而不是空集合通过。

## E04 [P2，审计状态] 只读重测的 PASS 没有纳入所有一致性字段

位置：`scripts/experiments/server_local_review.py:187-189`、`:238-242`。

`count_consistent`、`cost_matches_summary` 算出后不参与最终 status。磁盘里程碑缺失被标 NOT_AVAILABLE，但 `readback_consistent` 只遍历含 file 的记录；全部缺失时 `all()` 仍 True。只要没有抛异常，可以得到 PASS，同时成本/步数不一致或没有实际重测。

这是静态控制流确认，未造完整网络反例，未证明历史真实成本矛盾。脚本明确把科学结果设为 NOT_APPLICABLE，这是合理边界；仍应将读取完成、成本一致、磁盘重测完整分别报告，不能用一个 PASS 覆盖。

## E05 [P2，身份不足] 三个相同标量不能证明首个目标数组相同

位置：`scripts/experiments/server_failure_mechanism_audit.py:258-265`、`:384`，关联 tests_review 的 T07。

`same_first_target` 只比较 target_ss、target_count、loss_initial。对零预测，`[1,0]` 与 `[0,1]` 有相同这三项统计，却不是同一个目标。返回字段叫 identity_match，强于实际证据。

影响边界：当前零初态和固定源条件可能另有独立理由保证目标相同，不能由此声称实际两个首步不同；这一个布尔值本身不足以排除目标错位。建议比较输入、目标、支撑顺序和冻结配置的内容身份，或将字段改称统计一致，保留不确定性。

## E06 [P2，验收逻辑] 旧运行声明只需命中一部分输出即可 PASS

位置：`scripts/analysis/verify_claims.py:1274-1279`、`:1288-1305`。

R5 写明两个条件都必须满足，正则却只提取满足条件的行，且 run_claim 只要求至少一次匹配。只输出 `material_pair_ok 1` 即 PASS；再加一条明确矛盾的 `material_onesided_ok 1`，由于不匹配正则而被忽略，仍 PASS。lab320 的两个输出夹具已证实。

相同泛化器用于模式频率时，没有验证预期模式集合完整。另 `n2_p2_control`（1047-1055）只看 finite/误差/标签，不核128步；给0步空rows加好看的摘要也通过，已实测。

影响边界：现存历史执行是否确实输出全部模式/材料条件应看原始输出，不能从审核PASS反推。该历史入口已在 script_registry 封存，不建议直接重跑；当前主验收并不依赖此入口自动认证。建议对结构化输出做完整身份集合检查，矛盾/缺失分别失败或不完整。

## 其它已核对边界

- `stage2_fixed_state.py` 的 H/E 是固定参考状态的局部拟合诊断。E 目标可能保持基于精确固定场而非近似推进后的 H；它不能被当成连续闭环成绩，但文件本身已标固定状态，不另报为闭环算法bug。
- `run_fdtd_cavity.py` 用32间隔推得论文时间步不稳定，据此在注释里断言论文错误，超出了已确认信息。31间隔实现假设仍需分栏。零填充/抛物线插值提供更细的峰值估计，不等于延长观测物理时长；达到0.1%应由模式误差实际验证。发散路径只打印 return、没有明确非零退出或完整失败证据，故不能以 exit0认证参考成功。
- `r0_v2_audit.py`、`night_init.py`、`refine_night_storage_estimate.py` 和 p5 报告等有固定位置写入或固定历史结论。它们的封存登记是有效保护；只读审查没有执行入口或覆盖原证据。refine 脚本存在顶层写入，不能为查函数而直接导入。
- verify_claims 的旧因果 C 项已通过 AUDIT_NOTES 改为 REVIEW/RETRACTED，不能再把其中的旧代码结论一概称为当前认可的 PASS。它的 paper/grid/spacing/coverage 读取器有数据哈希与复算等有效检查，不能以 E06 抹去全部保护。
- verify_claims 的若干可选审核模式会写固定 findings/source snapshot/manifest；缺 `--md` 不代表纯只读。已封存的旧入口与当前新审计应分开，历史数据迁走后不应刷新为新的 NODATA/FAIL叙述。

## 对现状的解释

这里最明确需要收回的是 E01 的“非线性缺陷大小”和 E02 的“831.6倍同目标退化”解释，不是全部DCO训练结果。其它门的反例主要说明 **PASS证据不够完整**，不能把不完整一律升级为科学失败，也不能把已有失败改为通过。是否补测、修复或重新出图由用户决定。
