# P11 性能与 SSE 验证

`k6/p11-platform-and-sse.js` 并发创建必然被确定性策略拒绝的写操作任务，并为每个任务建立 SSE 连接。该场景经过 Java、Redis、Python LangGraph、策略拒绝和最终状态落库，但不会调用外部模型，因此不会产生 Token 费用。

默认阈值：错误率 `<1%`、创建任务 P95 `<2s`、收到终态 SSE P95 `<5s`。运行：

```bash
make stack-up
make p11-load
```

通过 `P11_VUS`、`P11_DURATION` 调整并发和时长。原始 k6 输出和测试环境必须与报告一起保存，不能把本地结果描述成公网容量上限。
