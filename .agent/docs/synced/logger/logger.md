未搬差异:

- `exceptiongroup` import 删除(3.14 内置);`patch_rich_traceback_extract` 未搬(py<3.11 专用)。
- `is_electron` 写死 `False`,不用 `env.ELECTRON`(OAS 无 Electron)。
- `oas/backend/worker/bridge.py` 是假 bridge,`inited=False`,日志只走 stdout+file。
- `logger.log_file` 不存在,对应 `LogWriter().file`;`script.py:118` 用 loguru 的 `logger.log_file`,切换时要改。
- `check_rotate()` 暂无调用者,Alasio 挂在 scheduler 循环与 8s GC 上,OAS 待找长循环接入,否则日志不按天切分。
- `logger.py:200` docstring 示例有误:`CaptureBackend.inited=True` 使 `_emit` 走 backend 分支,`capture.stdout` 恒空。Alasio 原版同样如此,未修。