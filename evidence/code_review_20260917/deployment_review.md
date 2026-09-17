# 部署、服务器队列与回传工具只读审查

日期：2026-09-17。工作区：`C:/PI-DON`。范围由用户指定，生产修复未授权，本报告只提出建议。

## 范围与结论边界

精确清单为 **59 个文件：12 个构建器、13 个独立安装器、16 个队列、17 个 ingest、1 个状态工具**。其中 **22 个完整读，37 个与完整读取的模板逐项差异审查，0 个待查**。构建器内嵌的 Python 安装器、队列和 PowerShell 启动脚本一并阅读。末尾逐文件表记录覆盖等级和本轮读取的 SHA256；开始、结束两次哈希一致。进度消息曾口头计为60，以本清单59为准。

本轮缩小的是“部署后的实际代码、预算、行动身份、回传文件与计划结论是否一致”的证据差距，不是重做科学训练或宣布论文复现成功。已读 AGENTS、PLAN、STATUS、总审查 REVIEW；只读执行 harness status/next 时使用 Python `-B`。status 成功，next 因已有迁移后证据路径缺失失败，未修改路径或状态。没有运行任何 installer/queue/ingest（包括其函数）、没有实验、没有新账本记录、没有子agent、没有解压落盘或故障注入。本轮唯一写入为本报告。

以下 D 编号仅属于本报告，避免抢占总报告 F 编号。P1 为关键预算/文件保护问题，P2 为条件触发的交付、追溯或结论可靠性问题，P3 为监控展示可靠性问题。静态确定的触发路径与历史上实际发生的事件分别说明。

## 新发现

### D01 [P1] 安装目标缺少规范化边界，能够越界或覆盖受保护账本

位置：
- `tools/install_server_128.py:32-42`；相同核心循环在64、micro4、micro16的32-42，first_e的30-40，batch2的34-44，clean64/128、step36e、step36e_low_lr、step36_window、step48_64的33-43。
- `tools/build_server_random_low_lr64_bundle.py:43-51`、`build_server_random_low_lr128_bundle.py:43-51`；`build_server_paper_tol128_bundle.py:60-68`。
- 首批 resource 安装器的特殊缺口：`tools/install_server_resource.py:28-34,42`。

触发：后续12个独立安装器直接使用 manifest 的 rel 拼接 src/dest，既不约束规范化后的根，也不禁止 project/records/evidence。三个内嵌安装器只检查名字以 payload/ 开头，再手动 open 目标；`payload/../../deployment-review-example.txt` 经 Windows 路径计算可落到 `C:/deployment-review-example.txt`，不经过 zipfile 的路径清洗。这个例子只做了字符串路径计算，没有创建文件。

resource 安装器确实有根路径限制，不能机械归入上述越界结论；但其账本黑名单检查原始字符串。`project/./plan.json`、`project\\actions.jsonl`、`records\\lab_runs.jsonl` 均不命中黑名单，规范化后却指向被保护文件；evidence 的覆盖保护也有同类分隔符别名缺口。

影响：异常包或错误 manifest 可覆盖根外文件、服务器计划、行动/成本账本或旧证据；文件哈希正确并不证明目标位置合法。**现存16个 server 部署包没有发现不安全成员名，不能说历史已经遭到越界写入。**

建议：统一规范化成员名，拒绝绝对/驱动器/父级路径，验证 source、destination、backup 三者的解析边界；按规范化后的目标执行受保护目录策略，再做写入。

### D02 [P2] 三个内嵌安装器生成了 manifest，却不读取校验；测试失败仍启动实验

位置：`tools/build_server_random_low_lr64_bundle.py:43-54,63-71`、`build_server_random_low_lr128_bundle.py:43-54,63-71`；`build_server_paper_tol128_bundle.py:35-43,58-71`。

触发：任一 payload 内容与 manifest 不符，或 unittest 返回非零。安装器仍从根目录中的固定 zip 直接覆盖目标，明确打印 Backup: none；测试返回码只 print，随后无条件执行队列。paper_tol 的 PACKAGE 变量完全未使用。安装器实际读取的是 ROOT 下固定名称 zip，不是其旁边已解压并查看过的 payload/manifest，混用两个版本时尤其容易装错。

影响：错误版本、未通过测试的代码可实际消耗GPU预算；服务器先前源码无备份。现存三个包的 payload 自身哈希本轮核对一致，random128包中内嵌安装代码也与当前构建器字符串一致。历史lab312/313确认相应训练执行，但没有取得安装测试的完整输出，**未证明它们曾在测试失败后启动或装到损坏内容**。

建议：绑定唯一包路径和摘要，首次写入前核完全部成员，备份变更源码，测试非零则退出。不要仅靠控制台打印哈希或返回码作为执行门。

### D03 [P1] batch2 根据“缺 summary”自动创建后继重试，无法区分零更新启动失败和已耗预算的中断

位置：`tools/server_batch2_queue.py:86-109,121-131,144-174`。对照冻结补充协议 `docs/plans/2026-09-15-server-batch2-recorder-fix.md:5-13`。

触发：某次训练已经更新参数，但进程在 summary 落盘前中断。下一次启动只看旧目录存在且没有 summary，就自动登记 R1…R5 并从初始化再跑；不检查旧行动是否结束、steps/checkpoint/心跳、已花更新或未知尾部。新任务ID使 harness 的“同一任务禁止重跑”检查不能阻止这条路径。它不是经过身份/预算核验的恢复。

影响：缺失终结文件成为获得新预算的条件，可能重复成本，甚至在上次进程仍运行时开启新臂。补充协议明示的是记录器错误后的独立修复任务，不能据此泛化成任意缺 summary 都可重试。

历史：保留的服务器账本lab298/299分别在 RunRecorder(mode="existing") 和非空目录检查处退出；两次是初始化故障，不能因本缺口宣称它们浪费了已执行训练预算。lab300的R2为exit0、3000 Adam、科学FAIL；该FAIL不改判。原始证据索引见下文H1。

建议：缺 summary 一律先记 INCOMPLETE，读取全部现存成本和行动状态。只有事前有独立问题、失败原因及预算依据的新任务才能执行；禁止由目录缺文件自动生成重试资格。

### D04 [P2] 队列登记的协议与运行产出的协议身份不同，已影响真实历史追溯

位置：`tools/server_micro4_queue.py:13,92,101-113`；`tools/server_batch2_queue.py:144,157,167-175`；`tools/server_step48_64_queue.py:13,92,102-115`。相关被调用代码仅为核对接口而阅读：`scripts/experiments/server_short_tol_probe.py:287-296,447`、`server_step36_window_probe.py:25,213-214,350-362`。

触发：micro4登记micro4协议，却未把 --protocol 传给短程入口，当前入口仍回落batch2。batch2的R1/R2行动登记recorder-fix，执行命令也未传该身份。48→64队列登记step48-64协议，却调用仍硬编码35→48协议的window入口，而且该入口没有协议参数。

历史证据：
- micro4部署包内旧探针在231-232行直接写batch2协议；保留的micro4回传报告也明确记录此错标；服务器lab302命令无 --protocol。
- step48-64部署包内探针在25、213-214行写step36-window协议；服务器lab308实际命令也无协议参数，而其行动start绑定step48-64（H1行动42行）。原始返回manifest当前不在原导入路径，不能声称本轮再次读取过该文件。
- micro16、strict64/128、clean64/128、paper_tol、random64/128队列都显式传了自己的 --protocol，不应一并指责。

影响：action通过的哈希与manifest/源码快照声称的协议不是同一份，恢复资格和预算追溯需要额外人工对照；这本身不证明物理更新错误或旧FAIL应改判。

建议：协议身份由同一已验证行动传入，运行前比对行动、参数、manifest；局部诊断应同时保留来源协议和本次协议，不能用另一个协议名代替本次身份。

### D05 [P2] PAPER01 生成的训练命令绕过统一行动校验，预检还绕过成本账本

位置：`tools/build_paper01_server_bundle.py:90-96,135-140`；`tools/build_paper01_theta_full_bundle.py:112-124`。

触发：两个生成队列先登记action，然后通过lab_log直接调用 _01/train_phase1*.py，没有 run.py --action，也不把行动ID传入实际训练。预检PS1更直接调用 _01/train_phase1.py preflight。读被调用入口确认其没有 require_action/PIDON_LAB 检查；preflight配置为2次Adam更新（`_01/train_phase1.py:24-28`）。

影响：正式训练期间没有统一入口对未结束行动和协议哈希的复核，lab argv及产出manifest也缺显式行动绑定；安装后直接运行预检将产生未登记、未通过lab_log记账的更新。训练文件自身的fresh目录拒绝覆盖仍有效，不将本问题解释为它会原地重训。

历史：theta服务器lab316的argv确实直接调用_01脚本，行动start/finish存在；它不是“没有行动”。本地lab302/303的已登记预检不能代替该服务器PS1路径的保障，也没有证据证明服务器实际执行过这个未记账预检命令。

建议：给独立_01入口建立与统一入口等价的行动/协议/输出绑定，再由生成命令显式传入；预检的2次更新单独登记和记账。不能只改变包装命令而遗漏训练端验证。

### D06 [P2] PAPER01 安装/收尾失败未传播，外层仍可显示训练成功

位置：`tools/build_paper01_server_bundle.py:116-131,144-149`；`tools/build_paper01_theta_full_bundle.py:143-162,166-172`。

触发：harness finish 因文件缺失、重复finish或账本写入失败返回非零。两个生成队列保存finish结果但从不检查，仍打回传包、打印status，最后只返回训练进程的返回码。两个PowerShell启动器也只设置 ErrorActionPreference="Stop"，未检查本机Windows PowerShell原生命令的 LASTEXITCODE；安装Python返回非零后仍可能继续下一个训练命令。

影响：账本未闭合或安装失败时，外层exit0/成功文字可掩盖不完整交付、并用部分安装后的源码训练。这是进程控制问题，不是训练数值判据。

历史：theta导入actions第58/59行均存在，实际这次finish完成，不能说本次收尾丢失。故障路径只经控制流审查，没有执行模拟installer/queue。

建议：逐步检查安装、训练、finish和打包的结果；分别保存训练状态与工程收尾状态。finish失败应保留可读证据并报INCOMPLETE/非零。

### D07 [P2] PAPER01-S1 重建部署包会携带本地终态和本地证据路径

位置：`tools/build_paper01_server_bundle.py:156-161,172`，内嵌安装器`:39-44`。

触发：当前工作树再次构建包。代码复制本地PAPER01-S1任务，仅清空depends；不会将本地PASS、scientific_result、evidence、summary剥离。目前本地该任务为交付PASS/科学FAIL_REGISTERED_S1_GATES，并引用本机imports和权重。新服务器没有该任务时将整项写入服务器计划，可能被harness因路径缺失阻止，或错误声明为本机已完成；因此不能正常作为fresh部署任务。

历史：现存server_paper01_bundle.zip内任务仍是READY、NOT_RUN、evidence=[]，说明首发包没有触发。theta构建器使用独立task_payload生成READY任务，避免了本问题；不要把两者混同。

建议：部署任务定义与主机上的执行结果分开；已完成任务不应通过重建包变成新的执行授权，也不能把本机结论复制成远端已经执行的证据。

### D08 [P2] 包哈希只覆盖增量文件，缺少实际运行依赖和源码身份的端到端绑定

位置：`tools/build_server_128_bundle.py:15-22,37-45`及其构建模板家族；`tools/install_server_128.py:26-45`及其安装模板家族；PAPER01打包/回传在`tools/build_paper01_server_bundle.py:22-37,121-129,162-176`、`tools/build_paper01_theta_full_bundle.py:29-44,148-160,194-209`。

触发：服务器已有pidon_recording、pidon_solve等依赖与本地版本不同。增量包manifest只列payload，不声明也不校验服务器已有基线版本；代表性128包仅6项，无src/pidon。安装只验这些文件、运行小范围测试或仅py_compile，然后启动。PAPER01两个包甚至没有逐文件安装manifest；theta侧car校验和由构建端生成，但安装器/PS1不读取。其回传主要是产出与账本，不包含实际运行Python源码快照。

影响：包自身哈希正确无法证明执行了预期的完整版本。这里不要求把所有依赖都重复打包，但必须验证未打包的依赖基线；运行后manifest记录某个版本也不等于开训前确认它就是冻结版本。

实际补查：
- 16个现存server部署包的manifest共检到有效成员，逐项哈希无不符；其中short/window探针包均未携带src/pidon核心。
- theta实际返回zip有14个成员、234,508,064解压字节，**没有.py源码或协议正文**。
- theta服务器lab316的25项outputs中，**0项属于paper01_theta_full_v1**，均为旧轨迹路径（19项有哈希、6项无哈希）；不能用这份列表证明theta全部产出已交叉核验。这是F14/F15在真实任务中的证据边界，不在本范围修改lab_log，也不臆断这些文件为何在运行期间发生变化。
- theta的summary仍含best/last各自哈希，本轮两项均比对一致；不能把“缺独立账本锚点”写成“权重哈希不符”或“训练没发生”。

建议：部署前验证完整依赖基线；保存实际执行的源码/协议清单和哈希；回传绑定action的全量产出manifest，不依赖截断的全工作区lab outputs。科学结论仍需独立指标重算。

### D09 [P2] 回传报告写死历史成败和解释，旧包重导还会覆盖当前全局判断

位置：
- `tools/ingest_server_batch2_return.py:101-102,165-169`固定0步、3000 Adam、FAIL；
- `tools/ingest_server_first_e_return.py:95-96,136,146-159`固定3769更新成功，scientific_result缺失还默认DIAGNOSTIC_PASS；
- `tools/ingest_server_micro4_return.py:119-120,185-194`、`ingest_server_micro16_return.py:119-120,177-187`固定微型通过；
- `tools/ingest_server_paper_tol128_return.py:152`固定64步Q约9.04%失败；
- `tools/ingest_server_random_low_lr64_return.py:152`固定随机通过且成本低于clean64，但并未读取对照成本；
- `tools/ingest_server_step36e_low_lr_return.py:85-89`即使最佳臂是5e-5，也写lr=1e-4通过。
- 全局回写代表：`tools/ingest_server_clean_low_lr128_return.py:245-266`、`ingest_server_clean_low_lr64_return.py:183-204`。

触发：同目录命名的输入是不同结果、INCOMPLETE、不同学习率臂，或在更新实验完成后重新导入旧包。表格可显示FAIL，正文却显示通过/固定数字。多份ingest还不比较事件时间或当前任务，直接改SHORT/LONG、清空current_task，覆盖固定review路径；导入历史证据即变成刷新全局现状。它们不在historical_entrypoints封存表中。

与F04/F17的区别：F04是相信输入摘要；这里即使摘要明确给出相反结果，解释仍不服从输入。F17是队列启动前重置任务；这里是回传旧结果覆盖后来的全局结论。

历史：保留报告中的micro4/16、first-E、paper_tol、random64数值恰与固定文字相符，未证明当时生成了相反结论；low-lr历史只执行1e-4一臂，本例没有错认5e-5。但这些“回传审计”不能当通用重新认证器。当前theta在plan中已PASS而STATUS仍写READY，说明本机文档/机器快照确有不同步；本轮不改写二者。

建议：先核对任务/action/协议身份，再从核验数据产生解释；旧包导入仅增添不可变索引，当前状态由明确的审核和时间顺序决定。缺失科学结果应INCOMPLETE，不能补成成功或确定失败。

### D10 [P2] 双学习率队列把部分完成当全任务FAIL，汇总成本只取一个臂

位置：`tools/server_step36e_low_lr_queue.py:107-150,152-163`；`tools/ingest_server_step36e_low_lr_return.py:46-53,80-82,165-181,221-237`。

触发：第一臂有FAIL摘要，第二臂已花更新但中断、没有摘要，或返回RESOURCE_LIMIT/INCOMPLETE。队列虽设置final_summary=None/rc_total，最后只要attempted非空便从已有摘要选best，写FAIL；未完成第二臂不进入evidence，attempts也只数有summary的臂。两臂都完整时，终结文字中的adam仍仅取best的new_adam_updates；ingest同样输出该单臂成本，不汇总失败臂。find_probes允许同名目录多次出现，rows_by_probe又按basename覆盖，可能混合不同尝试。

影响：资源或交付不足会变成确定科学失败；部分成本被遗漏且未知尾部不可见。协议的第二臂是“第一臂失败时才做”的条件臂，这个条件设计本身并不是bug。

历史：lab306只完成第一臂并PASS，5350 Adam，保存报告attempts=1，因此现有该次总数没有因两臂汇总而少计。故障和两臂分支仍须补强。

建议：区分未尝试、执行中断、资源限制和科学FAIL；按action/arm唯一身份汇总所有已知成本，未知尾部显式UNKNOWN，保留每个已启动臂的证据。

### D11 [P2] ingest 压缩处理未限制展开规模，也不拒绝同名/规范化冲突成员

位置：15个`ingest_server*_return.py`的safe_members及main提取调用；代表`tools/ingest_server_128_return.py:38-43,279-284`。PAPER01：`ingest_paper01_ablation_return.py:189-193`、`ingest_paper01_theta_full_return.py:36-41,136-141`。

触发：回传zip包含重复summary、Windows大小写/非法字符清洗后的同目标成员，或展开体积远超剩余磁盘。safe_members仅查开头/和..，没有成员数、总解压字节、压缩比、规范化目标唯一性或空间检查。后写成员覆盖先写成员。多数工具先复制原zip进import目录，再提取到同目录，也未拒绝成员名等于该zip文件名，可能破坏保留的原包副本。paper_tol/random64还不复制原zip，只保留展开结果。

重要排除：本机Python3.11 zipfile._extract_member会删除驱动器、绝对前缀与..，Windows下还清洗非法字符。因此，**不能仅因ablation使用extractall就宣称它有直接Zip Slip越界**。D01的手动dest.open写入则没有这层保护。

历史：检查过的16个server部署包无重复/不安全成员，theta返回包无Windows规范化冲突，最大压缩比约5.963；没有发现真实压缩炸弹或碰撞覆盖。其它历史已迁出的返回zip不在本机，未做全量安全认证。

建议：首次提取前验证全部成员、规范化唯一目标、类型/大小/总量及可用空间；原包存放在提取树之外，按哈希保留。异常包隔离为INCOMPLETE，不生成审核PASS。

### D12 [P3] 实时状态读取无法容忍正在追加的JSON尾行，准备数据阶段被显示为未开始

位置：`tools/paper01_ablation_status.py:24-48,66-75`。

触发：训练正追加history最后一行、summary正在写入，或中断留下不完整尾行；工具逐行json.loads，无异常边界，任一臂读失败导致全部状态命令退出。若已建立输出目录、正在生成样本但尚无history，工具仍写NOT_STARTED，不看manifest/样本文件/行动信息。

影响：监控可能在任务真实运行时失败或显示尚未开始，影响进度判断；不能据此判断进程卡死或重开预算。状态为RUNNING_OR_PARTIAL的措辞本身较保守，不应改成“它声称进程必定还活着”。

历史：本轮四臂/完整theta的现存history均可解析，未见残行；本轮没有实时轮询或运行该工具。

建议：读取最后完整记录并显式标注不完整尾部，单臂错误不要遮蔽其它臂；区分准备数据、已有部分产出与从未启动。

### D13 [P2] 构建覆盖旧包、安装边校验边覆盖，失败会留下丢失原包或混合版本

位置：`tools/build_server_128_bundle.py:34-43`及64/first_e/micro4/micro16模板；batch2的36-43；paper_tol的31-40；random64/128的59-69；PAPER01的`build_paper01_server_bundle.py:168`、`build_paper01_theta_full_bundle.py:202`。安装代表`tools/install_server_128.py:32-42`。

触发：固定路径包已存在，再构建时先unlink或ZipFile("w")，之后才逐个读取源码；中途缺文件/磁盘错误会丢失旧包且留下不完整新包。12个模板安装器每验过一个成员就覆盖一个目标，如果靠后的成员哈希错误，前面的正式源码已经变了；保留备份并不等于操作失败未生效。

影响：丢失用于追溯的精确部署包，或下一次运行使用混合版本。resource构建器用"x"拒绝覆盖，resource安装器也先预验全量哈希，应保留这两个较强行为，不能概括成全族完全一样；resource仍可能在后续“旧evidence冲突”检查处部分完成拷贝。

历史：当前已有部署zip可读且所列payload哈希一致，没有证据证明曾损失唯一原包或发生半安装。现存micro4包与当前探针源码版本不同是正常历史快照证据，不能用当前重新生成包替代原始包。

建议：构建写入新版本路径，完成验证后发布；安装先验证全清单和所有目标冲突，再以可追溯事务/明确回退方式应用，记录基线与新版本。原始证据和旧包不得原位刷新。

## 已确认问题的家族覆盖（不重复记新缺陷）

### F04

范围内17个ingest都没有形成“action + protocol +完整文件哈希 +成本/指标独立复核”的接受条件。15个server ingest主要读取summary及可选steps，随后写报告/plan；缺steps通常返回[]，部分缺manifest也读成{}。128/clean128还仅按summary.scientific_result将SHORT差距设为PASS。resource版本只看两个summary.status就将诊断任务标PASS并推进SR-DESIGN。ablation只验证PASS和4项，未验证四种唯一变体/更新数；theta只验证PASS和1项，未验证是否theta_min_0p5。这是F04的具体覆盖，不额外重复计数。

本轮可恢复的真实PAPER01结果并非只有一个空摘要：四臂各有连续[1..2000] history，theta有连续[1..25000]，learning_rate均为0.0001；10个best/last权重均存在且与各自summary哈希一致。ablation服务器lab315所列25项outputs本轮均能定位并匹配哈希。**这不等于所有产出和优化器实际step已独立认证**：没有加载checkpoint内部、没有重算场/模型指标；theta的lab产出锚点有D08所述实际缺口。

### F17

- 完整重置READY/NOT_RUN/evidence的9个队列：clean64、clean128、random64、random128、paper_tol128、step36e、step36e_low_lr、step36_window、step48_64。
- 部分重置status/depends的4个：micro4、micro16、64、128；不会都清空scientific_result/evidence，应与上一组区别。
- batch2强制重写SR-DESIGN为PASS，另有D03的自动重试；不是同一种完整任务重置。
- first_e只将BLOCKED改READY，仍无条件设置current_task；不能声称它也抹掉既有PASS的全部证据。
- resource的merge_tasks只增加不存在的任务，run_queue跳过有start的任务；它是该缺陷的反例。
- PAPER01 theta安装只保护PASS/FAIL，其它终态如INCOMPLETE/RESOURCE_LIMIT可被更新成新task定义（`build_paper01_theta_full_bundle.py:50-60`）；但同一任务已有start时harness仍拒绝再次登记，不能据状态重置就断言训练重跑。
- `server_128_queue.py:43-65,102-105`仅按旧summary的PASS_64自动提升依赖，属于F04/F17之间的额外调用点；现存strict64是FAIL，没有证据表明它实际误启动strict128。

所有这些入口都没有在本轮执行。原科学FAIL保持原判。

## 历史证据索引与剩余边界

H1：`evidence/server_resource_v1/dco_value_review_20260916_r1/returned/`内服务器`actions.jsonl`和`lab_runs.jsonl`。行动行22-27对应R0/R1/R2，30-31对应micro4，38-39对应低学习率单步，42-43对应48→64；lab行298、299、300、302、306、308、312、313与同名run ID对应。它们是已有回传副本，本轮仅读取。原`imports/server_*...`多已迁出，不能把不存在的路径当从未执行。

H2：`evidence/server_resource_v1/micro4_return_review.md`保留协议错标及4步、10558更新；`step36e_low_lr_return_review.md`保留单臂5350更新；`step48_64_return_review.md`保留16个新增步、61895更新。它们是历史报告，本文不把重新读取报告当重新认证原始权重。

H3：`evidence/paper01_s1/imports/server_paper01_ablation_return_20260917T045055Z/`；`evidence/paper01_s1/imports/server_paper01_theta_full_return_20260917T091252Z/`。本轮直接读history、summary、manifest、账本并流式哈希权重。theta账本`records/lab_runs.jsonl:316`为WS-04/GV100、exit0、9612.3秒；`project/actions.jsonl:58-59`有start/finish。theta历史训练完成的证据仍在，代码审查不将它改成NOT_RUN。

未进行：服务器现态检查、故障注入、安装/训练/ingest执行、checkpoint反序列化、全量场重算、已迁出返回包恢复。因此未将本报告写成科学PASS证书。随机/预训练128此前独立数值审计中的原FAIL，不因部署工具缺陷自动作废或改判。

建议用户优先决定：D01/D03的文件及预算边界，F04/F17的状态可信度，D04/D05/D08的行动与哈希追溯，然后处理报告与监控可靠性。这里没有任何修复已生效。

## 逐文件覆盖与源码哈希

“完整读”指本轮逐行阅读全部文件，包含内嵌脚本；“与模板差异审查”指与下列完整基准比较全部差异，未变化部分沿用基准分析。不是仅关键词扫描。B128=build_server_128_bundle；BR128=build_server_random_low_lr128_bundle；I128=install_server_128；Q128=server_128_queue；QC128=server_clean_low_lr128_queue；R128=ingest_server_128_return；RC64=ingest_server_clean_low_lr64_return；RM4=ingest_server_micro4_return；RW=ingest_server_step36_window_return；RP=ingest_server_paper_tol128_return（已与RC64逐差异阅读）。

| 文件（均在tools/） | 行数 | 实际阅读覆盖 | 比较基准/核查重点 | SHA256 |
|---|---:|---|---|---|
| `build_paper01_server_bundle.py` | 182 | 完整读 | 完整源码；包含内嵌INSTALLER/QUEUE/PS1 | `c87c87a3a55f59e9a05bd06b320a192351d532fa1444282df837615cbacdfc00` |
| `build_paper01_theta_full_bundle.py` | 219 | 完整读 | 完整源码；包含内嵌INSTALLER/QUEUE/PS1 | `05201d69cbdc12c3dfa993d61698150c8f3ba53633fc590aab00fffe2411fdd5` |
| `build_server_128_bundle.py` | 50 | 完整读 | 完整源码 | `29d9bc1a79956409c0595f3058e123b1c29786238e2fe69f9aa971c3a5a823d5` |
| `build_server_64_bundle.py` | 50 | 与模板差异审查 | B128 | `53344391c390eceb9f5bd0563d778a1f66e78b8d12c249136c89f5a6340cd452` |
| `build_server_batch2_bundle.py` | 51 | 与模板差异审查 | B128 | `b4596b1ccfb6f663bfddf7acfd43fd868bfb839691eed3ee3c430e1a03293905` |
| `build_server_first_e_bundle.py` | 50 | 与模板差异审查 | B128 | `5d03983ba36c6800d79b396de7b02bd837d2a17b7c1a453a1597d40e8c1ebabd` |
| `build_server_micro16_bundle.py` | 50 | 与模板差异审查 | B128 | `5de4d59cb804821cc209650ffa4140653b8a93ee40f3cc88ca5e13f8934ce4f9` |
| `build_server_micro4_bundle.py` | 50 | 与模板差异审查 | B128 | `b89f8dc3c0871fbc28d83b004e6b216d6c8df93e384c07f19ffb297c9d755864` |
| `build_server_paper_tol128_bundle.py` | 77 | 与模板差异审查 | BR128 | `cc38c2f6d502d099aef4d81b8b08b0a875e3c680840e4cc3e28c09d2cbc39eb1` |
| `build_server_random_low_lr128_bundle.py` | 76 | 完整读 | 完整源码；包含内嵌INSTALL | `721eaa2bc2960089f32923b148ad6a59e38d8e5b1c3690fcaae4065e778b0477` |
| `build_server_random_low_lr64_bundle.py` | 76 | 与模板差异审查 | BR128 | `72576384fafb830fa2eb1d127bbbc3826098e94542480a11e990ee0094de789d` |
| `build_server_resource_bundle.py` | 31 | 完整读 | 完整源码 | `eeec3c6ac166d56ebd00ca941908aeab00fc3f9f996629846feeb05ed32ff458` |
| `ingest_paper01_ablation_return.py` | 217 | 完整读 | 完整源码 | `1c11825e98449edffad9cf1f9bf3a85667df76ee06b65ba431a70b73d5381164` |
| `ingest_paper01_theta_full_return.py` | 166 | 完整读 | 完整源码 | `ebc957a04bb0355410b86083e80bf2df4982e45e89eadcbf39d83a07866db4ef` |
| `ingest_server_128_return.py` | 307 | 完整读 | 完整源码 | `89dad7f71e541a08da8a659aa5ab2dcde459f0bb51ba739e051d6f7a68fa3589` |
| `ingest_server_64_return.py` | 302 | 与模板差异审查 | R128 | `6bb83d730bd678e8462b77de7ccb6caa2488bf59c1068fdbad70f0afabf844bb` |
| `ingest_server_batch2_return.py` | 183 | 完整读 | 完整源码 | `13ffaf9e02d0bf2d7ec175664a66b1e35aa9b7242a4e2ea9efd9d17ebde75387` |
| `ingest_server_clean_low_lr128_return.py` | 307 | 与模板差异审查 | R128 | `3dd487ae68cdf53b67f8d13ea6f9e4816d68717d94774fb0689155a1fa899e09` |
| `ingest_server_clean_low_lr64_return.py` | 245 | 完整读 | 完整源码 | `1390fa8c771f583c9a7fbe5237d9e83c54cfb0ac983d6b77c1b5b16c39b48a67` |
| `ingest_server_first_e_return.py` | 211 | 完整读 | 完整源码 | `ea726dc4578a0041cdbafde19daf423beca16f4f81b65cb3974e5b459f0fffff` |
| `ingest_server_micro16_return.py` | 234 | 与模板差异审查 | RM4 | `bf0c156c310955840495fcd10552c09c6200662133c524220db564af2c057306` |
| `ingest_server_micro4_return.py` | 240 | 完整读 | 完整源码 | `59cd1a8e2217cf2e7332ecd4a3737ff11994e9123ed73669c9ff962efce14be6` |
| `ingest_server_paper_tol128_return.py` | 262 | 与模板差异审查 | RC64 | `2fae155bc51505316ef8ffeb74051fb460efabe3e0a5ab808feb0a20f3d3a4e8` |
| `ingest_server_random_low_lr64_return.py` | 263 | 与模板差异审查 | RP（另与RC64对比） | `29bde717c451474addaa7004fbaec81ffc60260e979ec08edab9c5054a3b01bc` |
| `ingest_server_resource_return.py` | 214 | 完整读 | 完整源码 | `62c65cda55a322f581d65b35d6409c878669d3fc91031d9bd913db6f844b1f26` |
| `ingest_server_step36_window_return.py` | 241 | 完整读 | 完整源码 | `a82272526047dfd83a4611f4435dedd656d7185c56a04ffc1c05c55a8d76306f` |
| `ingest_server_step36e_low_lr_return.py` | 245 | 完整读 | 完整源码 | `359832573a8291dd6523cb39f9855379873e6b2bbab4c4a7494e11146ed85ea3` |
| `ingest_server_step36e_return.py` | 222 | 与模板差异审查 | RW | `8a81bc90285d1c68bd64efb0eb060f9624df780465d11b2c9d59d072dca4ab86` |
| `ingest_server_step48_64_return.py` | 225 | 与模板差异审查 | RW | `7a8b564013951b7231b5b2d0ac1d98bfef00711e4ededcc047331cffd9aeaa95` |
| `install_server_128.py` | 49 | 完整读 | 完整源码 | `e53aceda981ae8457aa0583968d3dc8fb365b73523f4e2249eb3331ba037ecf2` |
| `install_server_64.py` | 49 | 与模板差异审查 | I128 | `d09a5cab73fb45bcf1187343621f368048ffb6e6ac0110b47099db2edd0678b5` |
| `install_server_batch2.py` | 51 | 与模板差异审查 | I128 | `c9beb1d807a076fc90e87ccb3fef6b86b0b1d7b21fee928c3e1a8d43b1e3125a` |
| `install_server_clean_low_lr128.py` | 52 | 与模板差异审查 | I128 | `53077c14694a97e264452aa5995090e6fe2ae1f8fd07425dac3710a415229b00` |
| `install_server_clean_low_lr64.py` | 52 | 与模板差异审查 | I128 | `826133fb4c96c22bfb35ed68c6a632c2bdf78e1fd353eaaca59dce3144f3bceb` |
| `install_server_first_e.py` | 48 | 与模板差异审查 | I128 | `39292b2c68d80a905fc53725dbfc66684262d8229ad5c28800d5d0ee7a0cf532` |
| `install_server_micro16.py` | 49 | 与模板差异审查 | I128 | `874c128f7cb3ae0eab1b9169eec6697be1f3d791970fee4d16c0abab1298cfcf` |
| `install_server_micro4.py` | 49 | 与模板差异审查 | I128 | `bc6eb531c4d9b3a37ed191ce924b5541420807a5c51955886c61fa89dd16b3e4` |
| `install_server_resource.py` | 56 | 完整读 | 完整源码；含规范化黑名单例外 | `6d3e46eb87a0865a9293c737874e07bbca509092d447ddcd9a73fe3adfe0b6ce` |
| `install_server_step36_window.py` | 52 | 与模板差异审查 | I128 | `6cdbfe10f013f66c07486669c6158bace52f2b90b8a298e3e8e0c67433a3357a` |
| `install_server_step36e.py` | 52 | 与模板差异审查 | I128 | `63dec642b161eff2384fe224b51c91d7771d3b47628d96c6838551884a143695` |
| `install_server_step36e_low_lr.py` | 52 | 与模板差异审查 | I128 | `a5e60a2a960397ada306c3dca27dcfb229fc6d9bd458dd2114f1038812b289ec` |
| `install_server_step48_64.py` | 52 | 与模板差异审查 | I128 | `6bb91d6479e6636df9e0c9120fc9eb181f6e0a816d0eec70abc1b3048d3e09d9` |
| `paper01_ablation_status.py` | 128 | 完整读 | 完整源码；JSON尾行与启动状态 | `bfde45232f1a7d4762028ce46eb4ee71477edcd4950a468e0bb4018bdf8f5b30` |
| `server_128_queue.py` | 171 | 完整读 | 完整源码 | `5c1febed55ce2815bad115f54b89385ec221bb439aabca72ecbe9bfe09374296` |
| `server_64_queue.py` | 138 | 与模板差异审查 | Q128 | `96f66fc4301d3c46b95421eedc38cd9d683c199ef6695c876c8161b74e3e3a67` |
| `server_batch2_queue.py` | 203 | 完整读 | 完整源码 | `e8f12063d75792846a4c961891899325afb2c4a15a9d71348f8492f01acd9ee5` |
| `server_clean_low_lr128_queue.py` | 143 | 完整读 | 完整源码 | `a9d245785f52d68704a934b9f31876c60aa167542df7b215bf2170ab556a2e65` |
| `server_clean_low_lr64_queue.py` | 142 | 与模板差异审查 | QC128 | `5f8362caea67dada8c3d45df5e8a891b134f8f25cf3b0a39a53aaa08d2138964` |
| `server_first_e_queue.py` | 133 | 与模板差异审查 | Q128 | `624cc526231cd25a2c3f300e5833eeb64e133c8442e51b180df525a7a235ecaf` |
| `server_micro16_queue.py` | 139 | 与模板差异审查 | Q128 | `12041e5d9d2a052e2018e06ed0cb9dd0dd8f7f0fdcd9e99b3ebb9bf241b0a7df` |
| `server_micro4_queue.py` | 138 | 与模板差异审查 | Q128 | `aa95fbfd385627504b12429ba903b0acedafa5c1bfad88078dd9e6153c1636e0` |
| `server_paper_tol128_queue.py` | 143 | 与模板差异审查 | QC128 | `aee69a5f73ad421f2d6cf94129deef32e906f13c60f91ed706185ff94404231a` |
| `server_random_low_lr128_queue.py` | 144 | 与模板差异审查 | QC128 | `6e6bb0b9b22b6d37f1c7a0ed507e39e963478325298aecb28d2b99e6d6a38c6b` |
| `server_random_low_lr64_queue.py` | 142 | 与模板差异审查 | QC128 | `291b5dffdf940200c7cdcda736f724cf43d666cfd5b1269b1e9c7f4404e26899` |
| `server_resource_queue.py` | 104 | 完整读 | 完整源码；F17反例 | `8436c35d83fb17b61a0565481c7c9acfa04efedbe18e2a189134c1b7fa11e86a` |
| `server_step36_window_queue.py` | 140 | 与模板差异审查 | QC128 | `5fe6eae4d3a1f0c6a52df813b3c7cd32bef0b7098089f27b7d681e46b9afecd5` |
| `server_step36e_low_lr_queue.py` | 169 | 与模板差异审查 | QC128 | `2d82ec73029e87c0a29a1afcf3f6365b8d7b26eaccb35cbb4e5c03b70d5d768b` |
| `server_step36e_queue.py` | 138 | 与模板差异审查 | QC128 | `210e2184b21c256337a1cbd1893c721d2d8918385e49d29aa9bbb4c0d8cdb6f4` |
| `server_step48_64_queue.py` | 140 | 与模板差异审查 | QC128 | `ba8774d1f694aab2500a0df7c0695faaa8487a980cedfc1b0999c62e1778e5f7` |

## 尚未检查的范围与版本边界

- **本轮指定的当前59文件：没有待查文件。** 差异审查的37个文件不是各自重新逐行阅读：本轮读取了各自完整文本用于diff，人工阅读了所有差异；相同行为的结论来自已完整阅读模板。覆盖表如实保留这一等级，不把家族推断标成59个完整读。
- **历史部署包版本：只做了有限核对，不是全部源码版本审查。** 对16个现存server部署zip检查了成员名/重复项、manifest所列payload哈希，并比对其中独立installer与当前tools版本；没有逐行读完每个历史payload。micro4包中的旧short探针、step48-64包中的window探针只定位阅读了协议与预算相关片段，D04对历史影响据此和服务器账本共同判断。三个内嵌安装器的后续版本判断主要来自当前构建器及本轮已读差异；random128现存zip内嵌INSTALL另外做了全文字符串相等检查。
- **PAPER01包：** 读取原S1/theta包中的任务定义；theta返回zip检查了成员和规范化碰撞。未执行任何内嵌代码，未声称当前构建器就是每次历史训练时的完整服务器源码。根目录ablation部署zip只顺带读取了成员元数据，它的构建器不在指定范围，不计为完整审查。
- **已迁出的历史证据：** 大量server imports中的原始summary/steps/manifest/checkpoint/zip不在当前路径；没有恢复、补造或跨盘搜索这些大文件。本报告对应条目明确使用“现存包/保留账本/历史报告”，不以报告替代对缺失原件的复核。
- **外部依赖与运行态：** run.py、harness、被调用实验入口、_01训练和Python标准库只为验证本范围的接口/控制流局部阅读，不在覆盖表中认领全量审查。服务器文件系统链接/权限、并发安装竞争、不同Python/PowerShell版本实机行为、所有运行时依赖版本、GPU中断恢复均未实测。
- **科学有效性：** 未重算模型输出、误差门、源外波形或反序列化优化器/RNG。PAPER01的连续history和文件哈希核对是交付证据补查，不将已暴露开发集提升为盲测，不修改F03/F10等已确认问题或旧FAIL。

本轮到此结束；只有此报告新增，所有建议均待用户自行决定是否修改。

