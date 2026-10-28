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
$env:OPENAI_BASE_URL='https://api.openai.com/v1'
$env:OPENAI_MODEL='gpt-4.1-mini'
# 在本机安全配置 OPENAI_API_KEY，不写入仓库或聊天
python -m src.main --mode live --input examples/inputs/conflict.json --db live.sqlite --trace examples/traces/local_live.json
```

程序读取进程环境变量，不自动加载 `.env`。默认 base URL 和 model 如上。模型工具参数严格校验，每轮只执行一个工具；无效响应最多两次，默认 8 轮、10 次工具调用，HTTP 超时 45 秒。超限或模型错误返回 incomplete，退出码 1。正常业务结果（含阻断、保存失败）退出码 0，应读取 JSON status。

**真实模型验收未完成。** 本次默认接口实际请求返回 HTTP 401，随后用户明确要求“不调用真实模型”，已停止调用。`normal_live.json` 是失败记录，没有成功模型动作，不能证明真实动态决策。mock 策略与 live 客户端独立，mock 不需要密钥。

## 示例与业务语义

`examples/inputs/` 包含正常、缺失、禁发、人工复核、冲突、明确确认、重复及保存失败输入。`examples/outputs/`、`examples/traces/` 是程序实际运行生成。`python -m examples.run_offline` 使用临时数据库重新生成隔离证据，并运行测试。

M01 的 18:00 被占用，hard 要求下建议 19:00，但不保存，返回 needs_confirmation。外部用户确认后使用 `confirmed_alternative.json`（新的 request_id）才保存。`--inject-save-failure` 显式模拟保存失败；`--max-steps 1` 验证 incomplete。

- completed：本地草稿操作完成，绝不是发布完成；published 始终 false。
- needs_confirmation：时间变更需用户确认，或风险需人工复核。人工复核风险目前没有自动放行入口。
- blocked：命中版权禁发规则；needs_information：关键资料补查后仍缺失。
- save_failed：工具保存失败，详情在 confirmation_items；incomplete：步骤/工具预算耗尽、模型错误或任务未处理完整。
- review_status：approved / review_required / blocked / insufficient_data。
- draft_status：saved / existing / not_saved / failed；保存结果来自实际工具回执。

合成假设：每个素材占用 60 分钟，候选以 60 分钟步长在之后 48 步内找最多 3 项（可请求 1–10 项）。时段采用 UTC 比较的半开区间，输出用户 IANA 时区。已有排期与草稿都占位，同批串行保存。待确认建议不持久化、不占位。soft 变更也记录原因；禁用替代建议时不会静默改期。

相同 request_id 的规范化完整输入绑定内容指纹；重复保存返回相同 ID。已保存后变更内容会返回 REQUEST_CONTENT_CONFLICT，需新 request_id；确认输入采用新 ID。SQLite BEGIN IMMEDIATE 内完成指纹检查、幂等检查、冲突复核、插入，唯一键用 SHA-256。规则与授权由服务端检查，模型不能覆盖。

## 限制

本地合成数据不可变，补查不会联系真实素材系统；因此 M02 补查仍缺失。多素材可能耗尽默认 8 轮，可明确提高 --max-steps，但仍有硬工具预算。候选并非预约，保存前再次复核；部分素材已保存后执行超限时保留实际保存状态，不回滚整批。SQLite 演示没有生产鉴权、取消草稿或发布接口。真实服务工具调用兼容性尚未验证。输入属于可信本地用户确认边界，不把模型输出当作用户确认。

当前目录不是 Git 仓库，未初始化、提交或推送；无法提供提交 SHA。个人贡献、实际投入时间及主观反思需本人填写。
