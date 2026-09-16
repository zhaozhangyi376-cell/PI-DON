# 本轮脚本与证据清单

此清单补充 [protocol.json](protocol.json) 的起始快照。协议建立后首次评估器进行了两次仅限字段兼容性的修复，诊断和台账读取器也在后续新增；它们的测试、修订和运行编号均保留，未回写为“初始快照”。

| 文件 | SHA-256 |
|---|---|
| `mechanism_decision_init.py` | `a04cb5436476db3fcb4da9705b496467910590a8a2819e7b95184c0dc6fd4248` |
| `mechanism_path_check.py` | `50d9f99e6faa4d749fe9192aa12477365977088b4c11bbf6e37a2f2d22692a0e` |
| `mechanism_decision_eval.py`（修订后） | `1f7a1bba4ab1a59858b1f11bc1d8da46c8777c9929af6bf5afb5dbd7d0be040d` |
| `mechanism_decision_runner.py` | `c2ad7ac9d318f04003c8e3ce608b69da59513d79df517810622da11f831c258b` |
| `mechanism_first_failure.py` | `b2b14a43790471ab184b21babd7aeb235072f1382d4a2d32f1754f899be184e9` |
| `test_mechanism_decision_eval.py` | `ccc5f354bc2db62789d9e74ae62c1dd4a39352a543d36561f48a55383cf5c5a9` |
| `test_mechanism_first_failure.py` | `2bf6b21be3a09b363f1bae68568dc087f63efd9dbee7ec2b8b48d8c4182a1f14` |
| `test_mechanism_claims.py` | `957bcf9da8474bbc1d18e0b4bf375424fed6adac769777b4594142033c8d3ea2` |
| `verify_claims.py`（包含Z0–Z3） | `f3de40700d60bc8b6f9629ea0bfe6b10f9d91c75bbb5318213d722624add40d9` |
| `mechanism_final_audit.py` | `50071e9e8f4b84bafd689f612f2b6eb724d919a1116fde106f2732a26c2b9bc9` |

关键运行：#223–225（合同和离散路径）、#226–231（评估器字段兼容修复及红/绿测试）、#232（S1）、#233（P）、#234（中止R）、#235–238（首次失败诊断的红/绿测试及出数）、#239–240（Z台账红/绿测试）、#241（Z台账只读复核）及#242（Y/Z合并复核并写入`RESULTS.md`）。详细命令、时间和输出哈希在 [LAB_NOTEBOOK.md](../../LAB_NOTEBOOK.md)。

在#241前有一次未成功记入台账编号的GBK输出异常：它只影响记账器向控制台转写旧文本，未改变任何数值产物。#241和#242均以Python UTF-8模式完成相同的只读核对；R臂的实际训练中止仍由#234和[EXECUTION_DEVIATION_01.md](EXECUTION_DEVIATION_01.md)界定。
