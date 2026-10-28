# 验收记录

2026-10-28 实际运行，模式 mock，模型 deterministic-mock-no-LLM。最近提交前回归结果：31 passed in 0.47s（此前 DeepSeek 接入时为 27 项）。命令与实际耗时见 [test_results](../examples/test_results.txt)。所有业务输出与 Trace 由程序自动生成；未手写成功日志。

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

另有人工风险复核、未知素材、offset/时区校验、半开边界、批内冲突、soft 改期、禁止替代建议、并发重复保存、恶意 finish 不得伪造成功、无效模型动作有界重试等测试。pytest 使用临时 SQLite，每次证据运行使用新临时库，重复场景共享同一库验证既有 ID。源码编译检查 `python -m compileall -q src tests examples/run_offline.py examples/run_live.py` 通过。

## 历史真实模型验收（2026-10-28，提交 5721eac）

用户重新授权接入 DeepSeek。实际服务 https://api.deepseek.com，模型 deepseek-flash。执行 `python -m examples.run_live`，退出码 0，8/8 通过，默认 max_steps=8 / max_tool_calls=10，实际总耗时 204.743 秒。凭据仅经隐藏输入进入临时进程环境，运行后已清除并退出进程；文件扫描未发现本次密钥。

[机器可读实际汇总](../examples/deepseek_live_results.json)。每组对应输入在 examples/inputs/，runner 的 CASES 显式列出映射。数据库使用临时目录，结果统计在关闭数据库前实际查询；不是模型自报。

| 场景 | 实际状态 / 保存状态 | DB 草稿数 | 秒 | 实际证据 |
|---|---|---|---|---|
| normal | completed / saved | 1 | 28.625 | [输出](../examples/outputs/deepseek_normal_live.json) / [Trace](../examples/traces/deepseek_normal_live.json) |
| missing | needs_information / not_saved | 0 | 22.783 | [输出](../examples/outputs/deepseek_missing_live.json) / [Trace](../examples/traces/deepseek_missing_live.json) |
| risk | blocked / not_saved | 0 | 22.464 | [输出](../examples/outputs/deepseek_risk_live.json) / [Trace](../examples/traces/deepseek_risk_live.json) |
| conflict | needs_confirmation / not_saved | 0 | 22.624 | [输出](../examples/outputs/deepseek_conflict_live.json) / [Trace](../examples/traces/deepseek_conflict_live.json) |
| confirmed_alternative | completed / saved | 1 | 28.184 | [输出](../examples/outputs/deepseek_confirmed_alternative_live.json) / [Trace](../examples/traces/deepseek_confirmed_alternative_live.json) |
| duplicate | completed / existing | 1 | 28.256 | [输出](../examples/outputs/deepseek_duplicate_live.json) / [Trace](../examples/traces/deepseek_duplicate_live.json) |
| save_failure | save_failed / failed | 0 | 28.302 | [输出](../examples/outputs/deepseek_save_failure_live.json) / [Trace](../examples/traces/deepseek_save_failure_live.json) |
| reoccupied | needs_confirmation / not_saved | 1 | 23.389 | [输出](../examples/outputs/deepseek_reoccupied_live.json) / [Trace](../examples/traces/deepseek_reoccupied_live.json) |

观察差异与真实后续动作：正常 query_slots.available=true 后，下一轮模型选 save_draft；冲突 query_slots.available=false 后，下一轮选 finish，并在公开理由中请求外部确认；缺失场景 check_rules 返回 insufficient_data 后，模型再次 get_material。Trace 的 next_action 来自下一轮实际响应。后验检查还核实了 normal 与 duplicate 的 draft_id 相同，草稿总数均为 1。

reoccupied 的 19:00 初始占位由本地工具显式准备（Trace fixture 标注），随后的模型查询观察到 20:00 为可用候选，结束请求确认，未新增草稿。不是模型自行授权或执行发布。保存失败使用显式故障注入，模型根据 SAVE_UNAVAILABLE 观察结束并报告失败。

接入中的真实错误也保留：旧 OpenAI 请求 HTTP 401 记录在 normal_live.json；DeepSeek 首次默认思考模式拒绝 tool_choice=required，诊断记录在 [probe Trace](../examples/traces/deepseek_probe_normal_live.json)。修复为官方域名下显式关闭思考模式后，本轮全部通过。risk 场景首次模型响应不符合单工具约束，应用拒绝并进行有界重试，随后完成阻断；此错误仍保留在成功 Trace 中。没有隐去失败或改写日志。

本次证明这些固定合成场景可运行，不构成广泛模型可靠性评测。API 费用未读取账单，不能报告确切金额。生产数据接入、鉴权和真实发布不在范围内。

## Definition of Done

- [x] CLI 可运行，mock 无密钥；DeepSeek live 实际调用成功。
- [x] 真实 LLM 完整循环成功执行，8 组代表性 live 场景通过。
- [x] 六项业务验收覆盖，T01–T10 离线自动测试通过。
- [x] 至少三组实际输入/输出/Trace（live 和 mock），正常、资料不足、保存失败均覆盖。
- [x] 至少两条真实模型动态决策路径：空闲→保存，冲突→待确认；另有缺失→补查与失败→停止。
- [x] hard 时间变更外部确认、风险不可绕过、待确认不占位。
- [x] 幂等、故障如实报告、步数与工具上限、输出始终 published=false。
- [x] README、五份文档、tests、examples、data、依赖与环境变量示例齐全。
- [x] 不提交密钥，不伪造 Trace 或成功记录；个人贡献和反思待本人填写。

## Git 与待本人完成项

初次交付时尚无 Git 仓库；随后按用户要求创建 main 并推送 https://github.com/largepineapple/shadow，初始提交 a97806ed9d6d28bb216348699a4cb1a74da7010d。当前 DeepSeek 接入与验收记录形成后续提交，可用 git log 核实。

仍待用户本人完成：个人贡献核实、实际投入时间、主观反思与最终评审权限确认。没有替用户捏造这些内容。运行耗时只代表自动验收脚本，不代表个人投入。工具预算和内容冲突等 T08/T10 的确定性测试已通过，本轮没有额外运行它们的 live 场景。

## 提交前最终质量检查

本轮保留既有 Agent Loop、工具契约、硬性规则和 SQLite 事务。仅在结果组装处增加每项 outcome_status，用服务端原有单项状态赋值；顶层仍为聚合摘要。确认来源已在 README、需求和方案中明确：confirmed_alternative_time 是可信外部 CLI 输入，不证明身份或同意真实性，当前不实现真实用户身份鉴权。

实际重新运行 `python -m examples.run_offline`，退出码 0：11 组离线示例生成成功，并调用 `python -m pytest -q`，31 项通过，耗时 0.47 秒；整个证据脚本耗时 3.947 秒，见 examples/test_results.txt。新增测试覆盖已保存项与禁发/缺失/人工复核项混合、预算耗尽后部分完成；另在原有批内冲突测试验证各项 outcome_status。

混合批次实际输入 [batch_mixed](../examples/inputs/batch_mixed.json)、[输出](../examples/outputs/batch_mixed_mock.json)、[Trace](../examples/traces/batch_mixed_mock.json)：顶层 blocked；M05 outcome_status=completed、draft_status=saved，M03 outcome_status=blocked、draft_status=not_saved。整体状态不代表所有素材均失败，也不回滚已保存项。

历史 live 一致性检查：8/8 汇总记录逐条与输出、Trace、模型名、动作顺序及保存状态一致；normal/duplicate 草稿 ID 相同。Git diff 确认历史 live 文件未改动；本轮没有再次调用真实模型。5721eac 的历史输出尚无 outcome_status，原样保留，不事后补写新字段；新增字段由本轮离线测试与示例验证。历史 API 兼容性和模型效果的证据仅适用于当时版本与那些场景。

文档相对文件链接检查、源码编译检查、git diff --check 均通过。README 与历史 DeepSeek 汇总的模型、场景数及状态相符。本轮全量检查确认，交付文档中实际待填写项只有以下两处；HANDOFF 原始规范中的 TODO 示例保持不变。以下内容应保留给候选人：

- docs/04-ai-usage.md：本人真实代码修改、技术取舍、验证工作、实际投入时间与贡献记录。
- docs/05-retrospective.md：本人理解、学到的内容、主观反思与实际投入时间。

这两处是最终提交材料仍待本人完成的内容，没有代写个人经历或宣称它们已完成。项目不包含真实发布接口或生产身份鉴权；两者都是明确范围边界。
