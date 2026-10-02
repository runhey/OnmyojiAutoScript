# ext/httpclient — 不搬

| 文件 | 行 | 依赖 | 调用方 | 测试 |
|---|---|---|---|---|
| `latency.py` | 259 | httpx / trio / msgspec | 0 | 0 |

`LatencyTest(urls)`：并发 HEAD 探测一组 URL，三阶段——`window=1s` 内回来的标 `In Window`，没收到就等最快那个标 `Fastest Fallback`，拿到答案立刻 `cancel_scope.cancel()` 掉其余，全局 `fail_after(timeout=5s)` 兜底。

不搬原因：无生产调用方、无测试、依赖 trio（OAS 未引入），且 `measure()` 内部 `trio.run()` 自开事件循环，只能当独立脚本用。

注：`alasio/git/fetch/transport_http.py`（172 行）是另一回事（git 协议 over HTTP），将来迁 `oas/git` 时带上。