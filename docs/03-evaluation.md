# 验收记录

2026-10-28 实际运行，模式 mock，模型 deterministic-mock-no-LLM。最近全套结果：24 passed in 0.31s。命令与实际耗时见 [test_results](../examples/test_results.txt)。所有业务输出与 Trace 由程序自动生成；未手写成功日志。

| ID | 场景 | 实际结果 | 证据 |
|---|---|---|---|
| T01 | 正常 | completed / saved | [输出](../examples/outputs/normal_mock.json) / [Trace](../examples/traces/normal_mock.json) |
| T02 | 资料不足并补查 | needs_information / not_saved | [输出](../examples/outputs/missing_mock.json) / [Trace](../examples/traces/missing_mock.json) |
| T03 | 硬阻断 | blocked / not_saved | [输出](../examples/outputs/risk_mock.json) / [Trace](../examples/traces/risk_mock.json) |
| T04 | hard 冲突 | needs_confirmation / not_saved | [输出](../examples/outputs/conflict_mock.json) / [Trace](../examples/traces/conflict_mock.json) |
| T05 | 外部确认替代 | completed / saved | [输出](../examples/outputs/confirmed_alternative_mock.json) / [Trace](../examples/traces/confirmed_alternative_mock.json) |
| T06 | 重复提交 | completed / existing | [输出](../examples/outputs/duplicate_mock.json) / [Trace](../examples/traces/duplicate_mock.json) |
| T07 | 保存故障 | save_failed / failed | [输出](../examples/outputs/save_failure_mock.json) / [Trace](../examples/traces/save_failure_mock.json) |
| T08 | 执行上限 | incomplete / not_saved | [输出](../examples/outputs/limits_mock.json) / [Trace](../examples/traces/limits_mock.json) |
| T09 | 候选再占用 | needs_confirmation / not_saved，建议20:00 | [输出](../examples/outputs/reoccupied_mock.json) / [Trace](../examples/traces/reoccupied_mock.json) |
| T10 | 同ID不同内容 | REQUEST_CONTENT_CONFLICT；不覆盖 | `tests/test_tools.py::test_failure_and_content_conflict` |

另有人工风险复核、未知素材、offset/时区校验、半开边界、批内冲突、soft 改期、禁止替代建议、并发重复保存、恶意 finish 不得伪造成功、无效模型动作有界重试等测试。pytest 使用临时 SQLite，每次证据运行使用新临时库，重复场景共享同一库验证既有 ID。源码编译检查 `python -m compileall -q src tests examples/run_offline.py` 通过。

## 真实模型情况

环境存在 API key，但没有设置 BASE_URL / MODEL，因此尝试默认接口及 gpt-4.1-mini。首次网络受限；获准联网重试后 HTTP 401。失败信息见 [实际 live 失败输出](../examples/outputs/normal_live.json) 与 [失败 Trace](../examples/traces/normal_live.json)。记录包含两次有界错误，没有成功模型工具调用。随后用户明确要求“不调用真实模型”，不再重试。

**未完成：** 真实 LLM 的动作→工具→观察→后续决策完整循环；至少两条不同工具结果下的真实动态决策 Trace；正常、资料不足、工具失败至少三组 live 成功运行证据，以及 live 冲突与重复路径。mock 不能替代这些验收项。

## Definition of Done

- [x] CLI 可运行，mock 无密钥；live 客户端实现实际 HTTP 请求，但兼容性/正常模型响应未验证。
- [ ] 真实 LLM 完整循环成功执行。
- [x] 六项业务验收覆盖，T01–T10 离线自动测试通过。
- [x] 至少三组实际输入/输出/Trace（mock），正常、资料不足、保存失败均覆盖。
- [ ] 至少两条真实模型动态决策路径。
- [x] hard 时间变更外部确认、风险不可绕过、待确认不占位。
- [x] 幂等、故障如实报告、步数与工具上限、输出始终 published=false。
- [x] README、五份文档、tests、examples、data、依赖与环境变量示例齐全。
- [x] 不提交密钥，不伪造 Trace 或成功记录；个人贡献和反思待本人填写。

## Git 与限制

`git status --short` 和 `git rev-parse HEAD` 实际均返回 `fatal: not a git repository (or any of the parent directories): .git`。未初始化、提交或推送，没有 SHA。运行耗时以自动报告为准，不代表用户个人投入时间。当前文件是可评审交付，完整 DoD 尚未达成。
