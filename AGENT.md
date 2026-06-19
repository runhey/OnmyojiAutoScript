# 单项任务测试流程

适用于单独修复、验证 `tasks/<Task>` 下的一个功能，不启动完整调度器。

## 1. 确认范围

- 从错误目录和主日志确认配置实例、任务名、设备及失败时间。
- 检查是否已有相同实例的任务进程，禁止两个进程同时操作同一设备。
- 保留工作区现有修改，只处理当前任务相关文件。

## 2. 定位问题

- 按时间顺序检查 `log/error/<timestamp>/log.txt` 和截图。
- 找到最后一次成功操作、未发生的预期操作及最终异常。
- 对照任务代码、资源定义和识别阈值，先证明原因再修改。

## 3. 最小修复

- 只修改导致失败的逻辑或资源参数。
- 资源由 JSON 等源文件生成时，同时更新源文件和运行时使用的生成文件。
- 不顺手处理无关警告或格式化无关代码。

## 4. 离线回归

- 优先使用真实失败截图，按项目实际算法验证识别结果。
- 记录命中坐标、匹配分数和阈值，断言分数高于阈值。
- 执行相关 Python 语法检查、JSON 解析和 `git diff --check`。

## 5. 完整运行

使用项目自带的 `toolkit/python.exe`，直接运行指定任务：

```powershell
./toolkit/python.exe -c "from module.logger import logger; from module.ocr.rpc import ensure_ocr_server_started; from script import Script; ensure_ocr_server_started(); logger.set_file_logger('oas2', do_cleanup=False); ok=Script('oas2').run('Hunt'); print('TASK_RESULT=' + str(ok)); raise SystemExit(0 if ok else 2)"
```

运行时替换配置名 `oas2` 和任务名 `Hunt`。持续查看对应的 `log/<date>_<config>.txt`，直到任务结束，不以“成功启动”作为测试通过。

## 6. 通过标准

必须同时满足：

- 修复涉及的目标操作在真实日志中成功执行。
- 任务进入核心流程并产生明确成功结果，例如 `Battle win`。
- 命令返回 `TASK_RESULT=True` 和退出码 `0`。
- `log/error` 没有生成新的错误目录。

若失败，保存新的错误目录和日志，重新定位后再运行；对于会消耗每日次数或资源的任务，避免无依据地连续重试。
