# 素材审核与发布排期 Agent

Python 3.11+ CLI，仅保存本地 SQLite 草稿。数据全部合成。评审先看 `docs/03-evaluation.md`、`examples/test_results.txt` 和 `examples/traces/`。

## 安装与运行

```powershell
python -m venv .venv
.venv/Scripts/Activate.ps1
python -m pip install -r requirements.txt
python -m src.main --mode mock --input examples/inputs/normal.json --db agent.sqlite --trace examples/traces/local_mock.json
python -m pytest -q
python -m examples.run_offline
```

本次受限环境依赖装在 `.deps/`，可先设置 `$env:PYTHONPATH='.deps'` 再执行命令。普通安装不需要此设置。

live 使用 OpenAI 兼容 Chat Completions HTTP 工具调用（标准库 urllib，无 SDK）：

```powershell
$env:OPENAI_BASE_URL='https://api.deepseek.com'
$env:OPENAI_MODEL='deepseek-flash'
# 在本机安全配置 OPENAI_API_KEY，不写入仓库或聊天
python -m src.main --mode live --input examples/inputs/conflict.json --db live.sqlite --trace examples/traces/local_live.json
```

程序读取进程环境变量，不自动加载 `.env`。未配置时默认使用 OpenAI 官方接口与 gpt-4.1-mini；DeepSeek 必须显式设置上述环境变量。模型工具参数严格校验，每轮只执行一个工具；无效响应最多两次，默认 8 轮、10 次工具调用，HTTP 超时 45 秒。超限或模型错误返回 incomplete，退出码 1。正常业务结果（含阻断、保存失败）退出码 0，应读取 JSON status。

**历史 DeepSeek 真实验收通过：8/8 场景。** 模型 deepseek-flash，正常、资料不足、规则阻断、冲突、确认、重复、保存失败、候选再占用均有实际输出和 Trace。本轮离线回归 31 项通过。详见 `docs/03-evaluation.md`。历史 `normal_live.json` 为旧 OpenAI HTTP 401 失败记录，`deepseek_probe_*` 为接入诊断 HTTP 400 失败记录，均如实保留。mock 与 live 独立，不能互相替代。

## 示例与业务语义

`examples/inputs/` 包含正常、缺失、禁发、人工复核、冲突、明确确认、重复及保存失败输入。`examples/outputs/`、`examples/traces/` 是程序实际运行生成。`python -m examples.run_offline` 使用临时数据库重新生成隔离证据，并运行测试。

M01 的 18:00 被占用，hard 要求下建议 19:00，但不保存，返回 needs_confirmation。外部用户确认后使用 `confirmed_alternative.json`（新的 request_id）才保存。`--inject-save-failure` 显式模拟保存失败；`--max-steps 1` 验证 incomplete。

- completed：本地草稿操作完成，绝不是发布完成；published 始终 false。
- needs_confirmation：时间变更需用户确认，或风险需人工复核。人工复核风险目前没有自动放行入口。
- blocked：命中版权禁发规则；needs_information：关键资料补查后仍缺失。
- save_failed：工具保存失败，详情在 confirmation_items；incomplete：步骤/工具预算耗尽、模型错误或任务未处理完整。
- review_status：approved / review_required / blocked / insufficient_data。
- draft_status：saved / existing / not_saved / failed；保存结果来自实际工具回执。
- outcome_status：每项素材独立的业务结果，沿用顶层 status 的枚举；不会因为同批其他素材阻断而抹去已保存结果。

顶层 status 是整批摘要，优先级为 incomplete > save_failed > blocked > needs_information > needs_confirmation > completed；达到执行上限等强制结果优先。批次不是一个整体事务：例如 M05 已保存、M03 被阻断，顶层为 blocked，但 M05 的 outcome_status=completed、draft_status=saved 和 draft_id 均保留。预算耗尽也不会撤销已保存草稿，应逐项检查 materials。`examples/inputs/batch_mixed.json` 演示该情况。

`confirmed_alternative_time` **是外部可信输入假设**：本地 CLI 的操作者负责核实用户已明确同意，再提供这个字段；程序仅验证时间匹配和规则边界，不证明操作者的身份、权限或同意来源真实性。当前不实现真实用户身份鉴权、签名确认或审批凭证。模型不能设置该字段。将来若接入服务端，需要在进入 Agent 前完成身份、权限及确认来源校验。

合成假设：每个素材占用 60 分钟，候选以 60 分钟步长在之后 48 步内找最多 3 项（可请求 1–10 项）。时段采用 UTC 比较的半开区间，输出用户 IANA 时区。已有排期与草稿都占位，同批串行保存。待确认建议不持久化、不占位。soft 变更也记录原因；禁用替代建议时不会静默改期。

相同 request_id 的规范化完整输入绑定内容指纹；重复保存返回相同 ID。已保存后变更内容会返回 REQUEST_CONTENT_CONFLICT，需新 request_id；确认输入采用新 ID。SQLite BEGIN IMMEDIATE 内完成指纹检查、幂等检查、冲突复核、插入，唯一键用 SHA-256。规则与授权由服务端检查，模型不能覆盖。

## 限制

本地合成数据不可变，补查不会联系真实素材系统；因此 M02 补查仍缺失。多素材可能耗尽默认 8 轮，可明确提高 --max-steps，但仍有硬工具预算。候选并非预约，保存前再次复核；部分素材已保存后执行超限时保留实际保存状态，不回滚整批。SQLite 演示没有生产鉴权、取消草稿或发布接口。已验证本次 DeepSeek 接口，其他服务/模型的兼容性仍需独立验证。输入属于可信本地用户确认边界，不把模型输出当作用户确认。

仓库：https://github.com/largepineapple/shadow，main 分支。初始提交 a97806e。个人贡献、实际投入时间及主观反思需本人填写。

## DeepSeek 真实验收

按上面的环境变量配置后执行：

```powershell
python -m examples.run_live
# 单场景诊断
python -m examples.run_live --cases conflict --prefix diagnostic
```

runner 使用真实 LiveClient、临时数据库、默认 8 轮/10 工具上限，逐场景自动核对实际状态、草稿数量、补查和替代时间；重复场景共享正常场景数据库。候选再占用场景显式用确定性本地工具设置初始占位，该场景随后的动作仍由真实模型选择。输出位于 examples/outputs/deepseek_*_live.json，Trace 位于 examples/traces/deepseek_*_live.json，汇总为 examples/deepseek_live_results.json。连接/响应失败会停止后续场景，runner 返回非零退出码。

DeepSeek 默认思考模式不支持当前 required 工具选择，客户端仅对 api.deepseek.com 显式设置 thinking.type=disabled；其他 OpenAI 兼容服务请求保持不变。不会记录隐藏推理。HTTP 错误保留脱敏诊断，并清除密钥。参考：[官方 API 文档](https://api-docs.deepseek.com/)。

提交前收尾只重跑离线测试与示例，并核对历史 live 文件，没有重新调用 DeepSeek。历史 live 输出属于 5721eac 版本，不含后来新增的 outcome_status；保留原始文件，不事后补写字段。新字段及混合批次行为由本轮离线测试验证。
