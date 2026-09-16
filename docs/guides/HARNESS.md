# 如何让每个动作都对准目标

项目只维护一个总目标。PLAN给路线，project/plan.json给任务状态，STATUS给最新证据；三者职责不同，不相互复制整段历史。

先看当前差距和待办：

```powershell
py -3.11 run.py project_harness status
```

检查前置与证据路径：

```powershell
py -3.11 run.py project_harness check
```

开始任务前登记。下面示例为下一轮M0，只登记不训练；问题与失败去向必须对应总计划。

```powershell
py -3.11 run.py project_harness start M0 --question "新运行的pending状态和实际成本能否完整保存并合法恢复？" --expected "受控暂停和不中断结果一致，失败重试消耗全部扣账" --success "针对性回归通过且原始计数/状态可逐项核对" --failure "保留工程失败，转M1可独立读数、S1准备与V，不启动依赖损坏接口的训练" --protocol docs/plans/2026-09-14-direct-mechanism-plan.md
```

记下返回的行动ID。数值运行如下，尖括号需要换成实际ID/已经实现的脚本：

```powershell
py -3.11 lab_log.py run -m "M0：pending恢复和计数验证" -- py -3.11 run.py --action <返回的行动ID> <已实现的脚本名> <参数>
```

root入口会拒绝没有lab_log/有效行动的实验主程序，拒绝已结束行动或被修改的协议；输出不能指向原模型或旧历史目录。新runner还须检查本臂/全局累计配额，harness本身不替代solver预算合同。

结束任务时，用finish追加结果。例如状态FAIL是对本行动交付的声明，不会自动修改科学结论：

```powershell
py -3.11 run.py project_harness finish <行动ID> --status FAIL --evidence evidence/<本实验>/REPORT.md evidence/<本实验>/audit.json --summary "具体失败点、原始证据和独立下一步"
```

然后审阅实际数值，再同步project/plan.json、PLAN和STATUS。**M2交付PASS可以包含实验FAIL；G128/G1024这类科学门只有全部数字通过才写PASS。** 有科学FAIL而分析已完成时，delivery任务可以完成，scientific_result仍FAIL。

next列出前置满足且没有执行过的任务。它只检查登记，详细计划中的科学条件仍要满足。RUNNING行动中断后应读未结束行动和原协议，不能再次start同任务重领预算。运行前source/data/config哈希由实验manifest冻结，动作登记的plan哈希不是替代。

没有软件能阻止agent绕过入口直接运行Python；这是一套可检查的工作约束，不是权限沙箱，也不是论文认证器。单元测试、文件存在、报告包含PASS均不能代替数值验收。
