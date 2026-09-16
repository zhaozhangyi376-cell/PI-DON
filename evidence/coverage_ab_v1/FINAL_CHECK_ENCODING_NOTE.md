# 最终复核的输出编码异常

在run #29之后，首次调用最终核验命令：

`py -3.11 lab_log.py run -m "里程碑4最终核验：12项检查与原始数组复算，保留T1/T2未通过结果" -- py -3.11 verify_claims.py --coverage-ab --run --md`

包装器显示预分配编号30，但尚未向lab_runs.jsonl或LAB_NOTEBOOK.md落账就异常退出。账本当时最后编号仍为29。关键堆栈：

```text
File "C:\PI-DON\lab_log.py", line 238, in do_run
    sys.stdout.write(line)
UnicodeEncodeError: 'gbk' codec can't encode character '\xb3' in position 36: illegal multibyte sequence
```

异常发生在日志转发，不是训练器。本次没有重新训练。不能把这次未落账调用称为完整成功的复核记录，也不能将其退出码解释成科学门槛FAIL。

恢复方法：在当前PowerShell进程设置`$env:PYTHONIOENCODING='utf-8'`，重跑同一核验，并在运行备注写明重试原因。预分配编号由账本决定，未落账调用没有独立的正式run记录。原始数组与权重由核验器重新校验哈希。
