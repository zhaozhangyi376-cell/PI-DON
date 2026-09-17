# 工作区重组与迁移工具只读审查

日期：2026-09-17。工作区：`C:/PI-DON`。本轮只交付问题和影响分析，修复待用户批准。

## 范围与方法

完整逐行阅读用户指定的七个 `tools/` 文件，共 **614 行**；不是按名字推断覆盖，也没有用模板差异替代全文阅读。末尾逐文件记录行数和 SHA256。开始、结束读取的七份源码哈希一致，也均与既有 `source_inventory.json` 相符。

本轮缩小的是“目录整理有没有保住证据身份，以及整理验收能否支持它声称的结论”的差距，不评价新的模型精度或论文复现成功。已读 AGENTS、PLAN、STATUS、总审查 REVIEW、deployment_review，以及本范围的历史整理计划和小型证据。使用用户指定的 dispatching-parallel 分工边界；没有再启动 agent。

严格按本轮“只读源码与现有小型证据”的要求，没有执行、导入或抽取调用七个被审脚本，没有运行其 `--help`、dry-run 或 apply，也没有运行实验、测试、harness、git 或模型反序列化。只通过 PowerShell 文件读取、JSON 解析、文件属性和 SHA256 做独立检查。唯一写入为本文件，使用 apply_patch；没有变更生产文件、账本、PLAN、STATUS、机器计划或旧审查报告。

根目录及 `scripts/` 的 storage/清理/迁移工具排查结果：

| 找到的候选 | 实际边界 | 本轮处理 |
|---|---|---|
| `scripts/analysis/audit_night_storage_revision.py` | 空间估算/清理后的审计，文件头声明不做清理；不是文件迁移器 | 只看前24行和文件操作关键词，不认领完整审查 |
| `scripts/experiments/refine_night_storage_estimate.py` | Adam 状态体积与空间预算估算 | 只看前24行和文件操作关键词，不认领完整审查 |
| `scripts/figures/export_storage_revision_handoff.py` | 计划交接导出，已在 `presentation_review.md:184,235,274` 覆盖 | 排除，不重复审查 |
| 根目录 `project_paths.py` | 路径解析兼容层，F07 已覆盖 | 排除，不重复审查 |

根目录文件清单和 `scripts/` 的 Python/PowerShell/shell/bat/cmd 文件中，未找到需新增认领的专用删除或搬迁工具。关键词扫描不是对任意隐藏实现的不存在证明，也不包含工作区外临时命令。新增认领文件数为 **0**。本报告不重复部署/ingest/harness 的 D/F 编号问题；相同风险类别在这里引用的是独占范围内的新调用点。

## 先说结果

发现 **8 项问题/风险**。L01、L02 涉及文件保护；L03、L04 涉及执行与恢复；L05、L06 涉及验收真实性；L07 有本轮直接观察到的备份字节追溯缺口；L08 涉及成本下界的证据条件。P1 表示可能直接误改文件或旧证据，P2 表示交付、恢复或结论可靠性问题。风险严重度不等于历史上已经发生。

本轮确认：233 个迁移目标全部仍存在；231 条移动事件的 before/after 哈希字段全部相等，保存的 proposal 与这231条事件的路径及 before 哈希一致；两份账本的原有前缀哈希相符。七份旧运行 JSONL 也仍与历史审计所列哈希、更新数一致。

同时，114 份 `before/root` Python 备份中，只有25份当前字节与登记的迁移前哈希相符，89份不符。84份在**内存中**把 CRLF 改成 LF 后与登记哈希相符；另5份未能通过本轮尝试的统一换行/BOM 转换解释。没有写回任何转换结果。不能由此推断模型权重损坏、全部科学结果无效，或认定是这七个脚本造成了后来的备份变化。

## 发现

### L01 [P1，条件风险] 修路径和收尾直接信任迁移表目标，可写到项目外或跟随链接改写其它文件

位置：`tools/repair_layout_paths.py:14-20,58-62`；`tools/finalize_layout.py:13-22`。对照 `tools/reorganize_workspace.py:67-72,86-87` 的显式包含关系检查。

两个后处理器直接执行 `ROOT / row['new']`，只按 `.py` 后缀筛选，随即读写。它们没有对迁移表做 schema/状态/规范化目标校验，没有拒绝绝对路径、`..`、符号链接或 junction，也没有在修改前比对登记的输入哈希。原移动器的 `contained()` 不会自动保护这些独立入口。

例如迁移表的某个 new 指向项目外现存 Python 文件，或已登记目录后来被替换为链接，修复器可以改写那个文件，并把改后的哈希写回迁移表。没有经过批准的文件会被当成正常布局适配对象。仅在移动器那里验证一次路径不够。

历史边界：本轮233个 new 字段均没有绝对路径或父级遍历；检查的 project/records/src/scripts/tools/evidence/before 目录和当前根文件未见 reparse point。没有证据证明历史发生过越界写入；没有创建链接或恶意迁移表测试。上述属性检查不是对所有历史祖先目录和并发替换的证明。

待批准建议：独立入口统一验证规范化后的源、目标、备份和父目录边界，拒绝不允许的链接/别名；限定已登记、未完成的迁移阶段，并在首次写入前核对全部输入哈希。后续测试应在临时目录覆盖绝对路径、父级路径、目录链接和文件链接，失败前任何目标都不应变化。

### L02 [P1，条件风险] 移动器解析源链接后 rename，会搬走链接指向的旧证据

位置：`tools/reorganize_workspace.py:67-72,84-91,109-112`。

`p.is_file()` 会接受指向普通文件的符号链接；`contained(p)` 返回解析后的真实路径。执行阶段把这个返回值赋给 p，再对 p 调用 `rename(q)`。如果根目录的 `alias.pt` 指向项目内 `evidence/.../checkpoint.pt`，包含关系检查会通过，实际被搬走的是 evidence 内的 checkpoint，原根目录链接则留下悬空。迁移表只记录 alias.pt，不记录实际移走的源位置。

这与“旧 evidence 原位保留”的承诺冲突，而且移动后内容哈希仍可完全相同，所以哈希相等无法发现这种位置身份错误。指向项目外的链接会被 contained 拒绝，应与项目内链接的缺口区分。

历史边界：当前根目录未发现这类文件链接，迁移事件也没有保存原文件类型，因此不能认证迁移时不存在链接，也不能声称这次已误搬证据。未做实际移动。

待批准建议：使用不跟随链接的文件类型检查，普通文件迁移默认拒绝链接；若明确支持链接，应记录并迁移链接本身，分别验证链接目标与位置合同。增加项目内证据链接的临时目录反例，确认 evidence 文件不变。

### L03 [P2，条件风险] 多个入口先改文件再完成前置检查或登记，失败会留下半完成状态

位置：`tools/finalize_layout.py:13-37`；`tools/repair_layout_paths.py:16-22,58-64`；`tools/reorganize_workspace.py:81-82,107-119`；`tools/build_project_state.py:47-62`。

具体路径不同，但共同问题是已生效的修改没有与可恢复的阶段记录同步：

- finalize 先无条件改写全部 Python 文件、重算内存中的 current 哈希，再检查两份目标账本是否存在。**当前两份 records 账本都存在**，此时重跑会在拒绝“已收尾”之前先写源码；源码写入可以规范化换行，迁移表则因后续异常没有保存。若第一次执行在移动第一份账本后失败，第二次也没有识别、验证并继续已完成部分的分支。
- repair 每修改一份文件就写盘，最后才保存迁移表和 path_repairs。中途碰到一个已适配文件、语法错误或写入失败，先前文件已经变动；再次运行又会在已插入的 bootstrap 标记处直接失败。
- reorganize 在移动前建立迁移表，但任何后续中断都使重试被“表已存在”拒绝。rename 后、事件写入前的窗口没有逐文件提交记录；哈希失败也是先搬走源，再报错。
- build_project_state 先写 plan.json，再用 `touch(exist_ok=False)` 建 actions，再读 migration_map 并写 registry。若 actions 已存在或 map 缺失/格式错，新的 plan 已经留下；重试又被 plan 存在保护挡住。它**不会在当前 plan 存在时直接重置计划**，不能把这里写成 F17 的完整重置问题。

影响：失败退出并不代表工作区未变化。恢复时可能面对源码、账本位置和迁移表不一致；手动删除挡路文件再重跑又会削弱原证据保护。finalize 的“无 logger 活动”只写在说明里，代码没有锁或静止性验证；并发写入时还需单独处理账本移动条件。

历史边界：当前移动事件231条、最终迁移表233条，后两条正是账本，不是凭数量就能指控漏搬。两份账本历史前缀均通过本轮哈希检查。现有记录未证明当时发生半迁移、并发丢账或错误重跑；本轮没有执行上述故障路径。

待批准建议：写入前预验全量源、目标冲突和阶段条件；用可核验的逐文件阶段日志及原子提交记录支持恢复，不能靠删除 manifest 重新领取迁移。收尾重跑应在任何写入前无副作用拒绝，或核对已完成项后明确继续。覆盖每个写入边界的故障测试，不自动回滚或覆盖用户后来编辑的源码。

### L04 [P2，部分已有记录] dry-run 不绑定 apply 的清单，apply 还覆盖先前 proposal

位置：`tools/reorganize_workspace.py:79-97,98-107`。

dry-run 与 apply 都重新枚举当时的根目录并计算清单。apply 没有读取、验证或接受一个已经审阅的 proposal/hash，而是先把新清单写到同一个 `migration_proposed.json`。两次调用之间新增、修改或删除的文件可能使实际搬迁范围与审阅范围不同；执行本身的 before/after 哈希只能证明 apply 时读到的字节被搬走。

此外，dry-run 也创建 OUT 并覆盖该固定 JSON，不能当成零写入检查。备份目录使用 exist_ok=True，copy2 也没有已有备份一致性检查；在迁移表尚未建立的失败重试中，旧备份可能被覆盖。

已有记录：lab265 是无 --apply 的执行，记录 proposal 哈希 `1a4cd0b5e323636f40efbea4e2cc61e0054bf400f04f963a45c90694662a7d4a`；lab266 是 --apply。当前 proposal 哈希为 `ec7c821f1a3e563f9f6a3f46e07eb66ae491c89bd935476870c64ec8c93ff9cc`，不是 lab265 记录的字节。当前 proposal 的231条路径/before 哈希与移动事件一致。**这证明原 dry-run 工件不能由当前同路径文件直接代替，不证明实际搬迁范围发生过未授权变化**；时间戳、序列化变化也会改变整体哈希。

待批准建议：proposal 使用新版本文件；apply 显式消费所审清单并验证其摘要及所有源文件仍一致，有变化就停止重新生成待审清单。备份必须拒绝覆盖或核验相同内容后复用。后续测试在 dry-run 后改变文件，apply 应在移动前拒绝。

### L05 [P2，条件风险] 布局校验没有把算法差异或实际测试执行纳入接受条件

位置：`tools/validate_workspace_layout.py:23-26,63-83,124-125`；`tools/write_reorganization_report.py:46-49`。

校验器只把函数/类 AST 差异存到结果中，并未判定是否属于允许的路径适配。`all_file_checks_pass` 只汇总存在、哈希、解析和原备份字段。AST 函数还排除了顶层常量/导入等语句，仅遍历 before 中的名字，新增定义也不会进入差异列表。迁移修改器自己写入的新哈希可以匹配一份行为已改变的源码。

与此同时，`loadTestsFromNames` 只是加载测试并枚举 ID，不运行测试；`execution_count` 实际是加载数量，`lab_log_id=268` 为常量。报告却固定写“核心 AST 完全一致”“内层拟合、场推进、指标数学未更改”“全部通过”。存在新 AST 差异、仅加载失败测试或后续代码变化时，这些结论并不会由实际结果自动收紧。

历史边界：保存的 layout_validation 当时列 dco/fdtd/contract/head_lstsq 差异为空，pidon_solve 仅列 formal_run_identity/Solver、Solver 方法为 _make_net；lab268/270/272 原账本退出码均为0。不能据此说当年测试根本没执行，或现在已证明发生数值算法改写。本问题是验收器与固定报告不能独立保障该结论。

待批准建议：分开输出文件完整性、允许的 AST 变化和测试执行证据；对完整模块 AST 或经过明确批准的变换做比较。测试通过必须绑定真实 runner 结果和源码版本，加载数命名为 collected_count。报告从这些独立检查派生，缺项 INCOMPLETE。后续负面测试应覆盖顶层物理常量改变、额外方法、求解方法改变及测试加载失败。

### L06 [P2，条件风险] audit 在断言前发布 JSON，报告可将失败审计标为 W0 PASS

位置：`tools/audit_reorganization_delivery.py:95-100`；消费者 `tools/write_reorganization_report.py:13-17,56-70`。

audit 先覆盖 `audit.json`，然后才断言成本、心跳/checkpoint 哈希和必需测试退出码。文件中没有“全部断言完成”的审计状态。报告只检查 migration_integrity、plan_validation_errors 和 unexpected_root_files 三项；没有检查成本/恢复断言、测试退出码或该 audit 进程是否成功。

因此，一次审计若仅因 lab268 失败、checkpoint 指针哈希不符或成本不等于预期而退出，仍可能留下满足报告三项检查的 JSON。随后报告会输出“全部通过”，并直接把 W0 写为 PASS。报告写盘、plan 更新和 actions 事件也不构成一次完整提交；actions 非空时根本不追加本次 W0 更新事件。

历史边界：当前保存 audit 的必需测试退出码、成本和布尔字段符合该次预期；本轮从账本看到 audit lab274 退出0。没有证据证明历史 W0 曾通过这条失败路径被错误标绿。本轮仅静态推导，未改数据制造反例。

待批准建议：审计结果明确标识完整状态和所有检查结果，完成检查后才发布；失败结果使用独立文件并标 INCOMPLETE/FAIL。报告应核对审计身份、版本和所有必要检查，写报告与变更任务状态分开；更新状态须留新的事件。失败测试/哈希/成本三类临时输入均不得生成 PASS。

### L07 [P2，当前证据缺口已确认] 交付器重用缓存 PASS，当前89份原源码备份已不匹配登记字节

位置：`tools/audit_reorganization_delivery.py:66,91`；`tools/write_reorganization_report.py:13-17,35,46-49,56-62`。实际原备份校验在 `tools/validate_workspace_layout.py:52-55`，前两个消费者没有重新调用同等检查，也没有绑定被查文件集合/版本。

当前旧 `layout_validation.json:1870` 仍记录 all_file_checks_pass=true，历史报告第37、56行声称原源码字节保留、备份哈希一致。本轮直接读取114份备份与 migration_map.sha256_before 比对，结果为25相符、89不符；84份仅把 CRLF 改LF即可匹配，下面5份在本轮尝试的原样/LF/CRLF和有/无BOM组合中仍未匹配：

| before/root 中的文件 | 登记 SHA256 | 当前 SHA256 |
|---|---|---|
| `dco.py` | `53eb1c7d7ea0ed33f4e6c279554cb1adaf4a86134b8dc60fd67f6ce39525941d` | `b2dc7240433c9dc3a9bfc3906d1bfc3141ded0dd2f7d4aa63e53a251a8d4b8d8` |
| `fdtd.py` | `9837dbe51bdbc89ab2a12c147debfb10b5db1d07ebc726d18ee1962ecda1e7a8` | `9512933f90cbb666fcf62d58af98e803e3fd04b5434f55099b27ef71313ac615` |
| `night_diagnostics.py` | `c62e4eea169e8d0941af2b23df64e115810abf6ce806024b792f50f2df8fcaa4` | `ef6d6d284f0e565614394cdfaf1e91482b6fdb9d09c5b2ce0da6467b9ecb3422` |
| `pidon_solve.py` | `3dd1c5559c86b59762935c0736263771e62884ca47fc5853c99b0b11e1703866` | `42109de3acfb35b422e3ff83025783a13104b40f8329050ff64edadf680d90c8` |
| `verify_claims.py` | `f3de40700d60bc8b6f9629ea0bfe6b10f9d91c75bbb5318213d722624add40d9` | `e6d9b07edc914032011bf048baa09ed6666bef05f977deeda3b0f70a8312ca4b` |

迁移表定位分别为 `project/migration_map.json:187,395,632,920,1830`。5份不能靠所试转换匹配，不等于已证明代码逻辑被改动；原始混合换行等情况也未被穷尽。变化时间、操作者和机制均未查明。**本报告不把备份漂移归因于这七个脚本，也不反推2026-09-14的校验必然错误。**

确定的代码缺口是：writer 可直接重用这份旧 true，重新覆盖历史报告、写 W0 PASS，而没有发现当前备份已经不符。普通历史报告可以保留当时结论；可执行的重新交付入口不能把它当作今天重新核验的结果。当前 writer 所用三项 audit 门均为通过，但本轮未执行 writer。

原审计版本也会被固定路径覆盖：lab269 记录 layout JSON 为57318字节/`c79744746f3c0c500cfe6fc83b9708f49656d37d1874576c6d072940802c20dc`；当前文件为lab273记录的66301字节/`38e362ef15a9987a8371ce3f8ff92c8fa46c9a88389aefc71112173ccbe2dce1`。audit 同样由lab271版本变成lab274版本。这里能确认同一路径被后续版本占用，不能据此断言全盘不存在其它原件。

影响：当前“原源码字节备份完整保留”应视为 **INCOMPLETE**，不能拿旧布局 PASS 认证今天的原字节追溯。它不自动否定旧模型、场轨迹或既有 FAIL；本轮未哈希全部模型，也未重算场。本轮7份旧运行 JSONL 均仍匹配原审计哈希，账本前缀也匹配，见后表。

待批准建议：保留原 manifest、备份和失败现场，单独登记当前不一致，不把新字节覆盖为旧 hash 的“正确版本”；历史报告和重审报告分目录保存。重新交付前核对证据版本和当前哈希。若需解释上述5份差异，应单独授权历史版本/原始归档追溯，不扩大本次到核心算法审查或跨盘恢复。

### L08 [P2，条件风险] 成本下界只凭 heartbeat 晚于 checkpoint 文件时间，未证明与已汇总日志不重叠

位置：`tools/audit_reorganization_delivery.py:60-63,79-84,96-97`。

代码用 heartbeat.updated_at 与 checkpoint 的文件 mtime 比较；只要前者更晚，就把 heartbeat.updates 整体加到所有完整 JSONL 的更新和中。它没有比较最后提交序号、heartbeat 所属物理步/attempt 和完整行的关系，也没有证明 heartbeat 的这些更新尚未计入 old_sum。文件复制还能改变 mtime，而不改变状态内容。

如果 checkpoint 落后于 JSONL、心跳对应已经提交的拟合过程，或复制使 mtime 变化，这个规则可能重复相加、遗漏尾部，或拒绝原本相同的证据。特别是“下界”不能由可能重复的两项相加得出；哈希相符也不能代替成本集合不重叠的证明。

历史边界：现存 S_P_retry 指针序号为5，JSONL为唯一连续0..5；最后完整步 H/E 为363/381，完整和10447。心跳内容是 H、183更新；checkpoint 文件时间仍为2026-09-14T02:37:07.4396565Z，心跳内时间为02:37:21.232511Z。已有独立审计还记录了当时末步后的现场关系。因此本轮**没有证据推翻原已知下界35122**；没有加载 checkpoint 内部重新认证，也不能把下界升级为精确总数。

待批准建议：尾部身份应包含运行、物理步、半步、attempt 和已提交序号；通过同一身份的增量/累计规则判定不重叠。mtime 只作旁证，无法确定时报告 UNKNOWN/可证下界。后续测试覆盖落后checkpoint、重复心跳以及仅改变复制时间的相同内容。

## 已核对的历史证据及影响

以下是读取原 JSONL 的独立汇总，不调用被审脚本。七个文件的当前 SHA256 均与保存 audit 的 steps_sha256 相同。

| 原运行 | 完整JSONL行数 | 本轮汇总 n_updates | 原审计数字 |
|---|---:|---:|---:|
| mechanism_1h_v2 / D_LR | 1 | 657 | 657 |
| mechanism_1h_v2 / S_P | 1 | 1 | 1 |
| mechanism_1h_v2 / S_P_retry | 6 | 10447 | 10447 |
| mechanism_1h_v2 / S_R | 34 | 10070 | 10070 |
| mechanism_1h_v2 / X_R | 42 | 13764 | 13764 |
| mechanism_2h_v1 / D_LR4 | 1 | 645 | 645 |
| mechanism_2h_v1 / D_LR4_retry | 2 | 4074 | 4074 |

一小时完整行更新和为34939；两小时两次独立运行更新和为4719。这里只认证这些原记录的完整行汇总，不认证所有未落行尾部、执行账本或模型内部 optimizer 状态。原科学 FAIL、不具备正式恢复资格，以及不能把两个独立首步拼接成连续轨迹的边界均保留。

账本原前缀验证：`records/LAB_NOTEBOOK.md` 前621607字节 SHA256 为 `e7ab13b338c824adee97042699f90ab63fd4c95ec3f8622001a49d1379032eba`；`records/lab_runs.jsonl` 前789805字节为 `03819be34cd0177c5b8b4feef373e89c321389fe0bd9f060bb061204224cbac6`。两者都与迁移登记值相符，后续追加部分不参与这个旧前缀比较。

未发现这些脚本直接删除旧模型/数组的代码。普通文件的移动器确实有 ROOT 包含检查、目标已存在拒绝、逐文件前后哈希和事件追加；build_project_state 确实保护已存在的 plan。这些有效保护不应因上述缺口被忽略，但不能替代链接身份、事务恢复和当前证据复核。

## 逐文件真实覆盖

| 文件 | 行数 | 实际阅读覆盖与主要结论 | SHA256 |
|---|---:|---|---|
| `tools/audit_reorganization_delivery.py` | 108 | 全文1-108；JSONL汇总、心跳/指针、缓存校验、断言与发布；L06/L07/L08 | `e410d0013931590a9a0dc970ee0ddd472c3689639075ca026d20e31c8499b90c` |
| `tools/build_project_state.py` | 67 | 全文1-67；初始任务、已存在plan保护、actions/registry提交顺序；L03 | `e676e588ff3f9fe60c2d19fa1175f7c53eeef7cf0731e5d420ef82823c9b22d2` |
| `tools/finalize_layout.py` | 42 | 全文1-42；路径修复、哈希回写、账本移动与重跑顺序；L01/L03 | `10aa9b652d4f5061d850db29124971ce1a6060fa688850eda088aceea5bf9150` |
| `tools/reorganize_workspace.py` | 124 | 全文1-124；分类、containment、链接、备份、proposal/apply和移动事件；L02/L03/L04 | `861f95f4a226b820fa05f50e0172968e797c02a875c77a1adb6f8b2ff3f1dd50` |
| `tools/repair_layout_paths.py` | 69 | 全文1-69；AST插入、文本替换、原地写入、输入哈希缺口；L01/L03，算法零编辑声明须受L05限制 | `dc2e52eb04c24875c543ad44a9bcc57c6f2c7d0d7f11455b7c75f5552f81d315` |
| `tools/validate_workspace_layout.py` | 129 | 全文1-129；旧前缀/原备份校验、AST范围、测试加载、索引与资产读取；L05/L07 | `ba985ab91b29b7c70396eaa0efaa5e12fc65618e741c84bee100d2e12338c43d` |
| `tools/write_reorganization_report.py` | 75 | 全文1-75；输入门、固定结论、报告/计划/事件写入；L05/L06/L07 | `402cf1af604d059e62d6b1ddad67803786b3313bad508cf130e6e6aebcac9f44` |

以上为当前源码版本审查，不声称每个历史执行版本与之字节相同。备份仅为验证身份而读取字节，没有认领114份备份的算法审查。

本轮关键小型证据快照：

| 文件 | SHA256 |
|---|---|
| `project/migration_map.json` | `e190e3319df1f279360c290d4d154ad99a6c9add9d61c1f6f636d7b3207d9af3` |
| `evidence/workspace_reorganization_20260914/audit.json` | `f90a80816e7b2d4703e62fdb50a99857f5932a631f211933e3e9d1bcfc71d672` |
| `evidence/workspace_reorganization_20260914/layout_validation.json` | `38e362ef15a9987a8371ce3f8ff92c8fa46c9a88389aefc71112173ccbe2dce1` |
| `evidence/workspace_reorganization_20260914/migration_proposed.json` | `ec7c821f1a3e563f9f6a3f46e07eb66ae491c89bd935476870c64ec8c93ff9cc` |
| `evidence/workspace_reorganization_20260914/migration_events.jsonl` | `5ce834be4d48808bb5fbe503a7a91f183e9371702717a8757fa344b298e2bbb8` |

## 剩余边界与建议顺序

七个指定文件无待读部分。修复、故障注入、链接实测、全量模型/数组哈希、checkpoint反序列化和场误差重算均 **NOT_RUN**。本轮没有评估 Windows 并发重命名竞争或断电持久性，也没有寻找跨盘原始归档。当前源码备份的原字节追溯为 **INCOMPLETE**，变化原因未判定。

建议首先批准文件目标和重跑保护（L01-L04），随后补齐审计完成状态与版本绑定（L05-L07）；L08随历史成本重新认证处理。现有历史证据应保留，新验证使用新输出位置。未授权任何生产修复，本报告没有改变旧科学结论。
