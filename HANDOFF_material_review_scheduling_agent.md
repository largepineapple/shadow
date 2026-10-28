# Handoff — 素材审核与发布排期 Agent

> 小影科技 2027 校招 AI Agent 项目题 1。交给 Codex 的实现规范。请以实际运行结果为准，不要伪造 Trace、测试结果或个人贡献。

## 0. Codex 执行指令

你是负责实现此仓库的工程助手。请按本手册完成可运行的 Python CLI 项目，优先实现完整核心链路而非 UI、多 Agent 或生产级 Runtime。先检查当前仓库，再创建/修改文件。每完成一个阶段运行相应测试；最终运行全套测试并给出命令、结果、未完成项。不要擅自执行真实发布、推送到远程仓库或提交真实密钥。真实 LLM 未配置时只能运行离线 Mock，并明确其不能证明真实模型决策效果。不要编造模型调用或成功记录。

## 1. 业务需求与成功标准

**用户**：内容运营/审核团队。**目标**：输入素材 ID、素材元数据、发布时间要求、已有排期及审核规则，输出每项素材的审核状态、风险原因、建议时段、待确认项和草稿保存状态。系统仅保存草稿，不连接发布平台。

必须覆盖六项验收：
1. 正常排期：无风险、时段空闲，产生合法草稿。
2. 素材信息缺失：主动补查；仍缺失则标明待补充，不能假装审核通过。
3. 规则风险：返回规则编号、原因、阻断/待复核状态；硬阻断不得排期。
4. 时段冲突：模型依据查询结果选择替代时段或请求确认；硬性时间不可静默修改。
5. 重复提交：相同逻辑请求多次保存只产生一份草稿，返回既有草稿 ID。
6. 保存失败：准确返回失败和错误原因，不得输出“保存成功”。

此外：必须至少有一个真实 LLM 驱动的“模型选动作→工具→观察→模型调整/结束”循环；至少两条真实模型执行路径因工具结果不同而采取不同后续动作；设置最大执行步数/工具调用上限，超限明确返回 `incomplete`。

## 2. 范围与技术取舍

- Python 3.11+，CLI，原生 Agent Loop；模型通过 OpenAI 兼容 API 接入，环境变量配置 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`。可使用官方 `openai` Python SDK，锁定依赖版本。
- 业务工具是本地 Python 函数，读取 `data/` 中的合成 JSON；草稿存 SQLite（标准库），方便证明持久化、唯一性和原子性。
- `--mode live` 使用真实 LLM 工具调用；`--mode mock` 使用显式标记的确定性策略，仅做流程/工具/集成测试。两种模式日志严格区分。
- 不实现 Web UI、线上发布、真实用户鉴权、多 Agent、复杂 RAG。不得为满足 ReAct 验收而用硬编码分支代替真实模型决策。

## 3. 业务模型

### 3.1 输入

建议 CLI：

```bash
python -m src.main --mode live --input examples/inputs/conflict.json --db /tmp/agent_demo.sqlite --trace examples/traces/conflict_live.json
python -m src.main --mode mock --input examples/inputs/normal.json --db /tmp/agent_demo.sqlite --trace examples/traces/normal_mock.json
```

输入 JSON 结构示例：

```json
{
  "request_id": "req-conflict-001",
  "material_ids": ["M01"],
  "platform": "short_video",
  "requested_time": "2026-11-03T18:00:00+08:00",
  "time_requirement": "hard",
  "timezone": "Asia/Shanghai",
  "allow_alternative_suggestion": true,
  "confirmed_alternative_time": null
}
```

`time_requirement` 为 `hard` 时，原时段是用户硬性要求：可提出替代建议，但不得未经用户明确确认就将建议时段作为获批准的排期。`confirmed_alternative_time` 只能由外部用户输入提供，模型不得自行写入。对于软性时间也应记录实际改动及原因，避免隐性修改。

### 3.2 输出

统一 JSON 结果（每素材一项）：

```json
{
  "request_id": "req-conflict-001",
  "status": "needs_confirmation",
  "materials": [{
    "material_id": "M01",
    "review_status": "approved",
    "risk_reasons": [],
    "requested_time": "2026-11-03T18:00:00+08:00",
    "suggested_time": "2026-11-03T19:00:00+08:00",
    "confirmation_items": ["原要求18:00已占用；请确认是否改为19:00"],
    "draft_status": "not_saved",
    "draft_id": null
  }],
  "published": false,
  "reason": "Awaiting explicit user confirmation"
}
```

状态枚举建议：`completed`, `needs_confirmation`, `blocked`, `needs_information`, `save_failed`, `incomplete`；审核状态 `approved`, `review_required`, `blocked`, `insufficient_data`；保存状态 `saved`, `existing`, `not_saved`, `failed`。必须在文档中定义语义：`completed` 表示本地草稿操作完成，不是发布完成。

### 3.3 数据

`data/materials.json`：M01 正常、M02 缺少关键元数据、M03 命中硬性禁发规则、M04 命中需人工复核的风险、M05 正常。字段至少含 `id`, `title`, `duration_seconds`, `copyright_status`, `sensitive_flags`, `review_notes`。`data/schedule.json`：已有排期（平台、起止时间、状态）；含 M01 请求的 18:00 冲突和 19:00 空闲的例子。`data/rules.json`：声明必填字段、版权禁发规则、敏感内容复核规则、时段占用判定及候选时间步长。数据必须为合成数据。

统一时区：输入含 offset；解析为 timezone-aware datetime，内部统一 UTC 比较，输出保留用户时区。时段冲突使用半开区间 `[start, end)`，不是只比较时间字符串。建议将每条发布占用时长配置为 60 分钟，并在文档明确这是合成业务假设。多素材按平台、时间和已有排期逐个检查，避免同一批草稿内部互相冲突。

## 4. 工具契约与安全边界

工具必须返回结构化 JSON（`ok`, `data`, `error`），错误可观察；不向模型暴露真实数据库写入接口以外的任意代码执行。

1. `get_material(material_id)`：读取素材及元数据；不存在返回 `NOT_FOUND`。
2. `check_rules(material_id)`：依据 `rules.json` 和素材元数据确定 `approved` / `review_required` / `blocked` / `insufficient_data`，返回命中规则 ID、风险理由、缺失字段；**规则结果由确定性代码执行，LLM 不能覆盖硬阻断**。
3. `query_slots(platform, requested_time, candidate_count=3)`：返回指定时段冲突情况及可用候选时段；候选时段只是建议，不是用户授权。
4. `save_draft(request_id, material_id, proposed_time, confirmation_state, ...)`：服务端强制复查规则、时段和授权边界；禁止硬阻断、未确认硬性时间变更及冲突时段被保存为已批准排期。对待确认的替代时间，建议**不保存排期草稿**，只在最终响应中提供建议；也可单独保存 `pending_confirmation` 的非占位提案，但必须明确其不占用时段且不表示确认。优先采用前者，降低歧义。
5. `get_draft_by_key(idempotency_key)`：可选；支持模型/业务层检查重复提交。

**关键设计**：LLM 负责决定调用哪个工具、如何根据观察选择下一步；工具层/应用层强制执行硬规则。`save_draft` 必须在同一个 SQLite 事务内做幂等检查与插入，`idempotency_key` 唯一约束；并在事务中复核草稿与已有占用冲突（单进程 SQLite demo 即可）。相同业务请求使用规范化请求内容计算 SHA-256 幂等键，例如 `(request_id, material_id, platform, requested_time, approved_time)`；相同键返回原草稿 ID 和 `existing`，不重复插入。若相同 `request_id` 携带不同业务内容，应明确冲突或使用定义清楚的版本语义，不能默默覆盖。

故障注入：为测试保存失败，使用显式 `--inject-save-failure` 或独立故障工具适配器，不修改真实结果或事后伪造日志。工具失败可返回 `SAVE_UNAVAILABLE`。模型可选择停止并报告失败；不得称已保存。

## 5. Agent Loop

每一轮：
1. 将用户请求、当前工具列表、之前工具观察传给真实 LLM。
2. 模型选择工具调用（含参数）或结构化结束动作。
3. 应用层校验工具名和参数；执行工具并捕获异常。
4. 将工具结果作为观察消息回填给模型；模型重新决定补查、找替代时段、请求确认、阻断或完成。
5. 每次记录 step、tool、arguments、observation_summary、next_action、decision_basis（仅简短可公开理由，不记录内部 chain-of-thought）。
6. 达到 `max_steps=8` 或 `max_tool_calls=10`，返回 `status=incomplete`，说明限制及已完成内容。

模型系统指令要明确：不能伪造工具结果、不能修改硬性发布时间、不能绕过审核阻断、不能宣称发布成功、保存状态必须取自工具结果、工具返回错误时可调整动作但不能凭空补全结果。模型输出由 JSON Schema/Pydantic 或严格校验器检查；错误响应至多进行有界重试。保存成功状态应由应用层根据真实工具返回生成/校验，而不是信任模型自由文本。

特别注意：示例的 `M01 18:00冲突→19:00可用` 在 `time_requirement=hard` 时应输出 `needs_confirmation` 和 `draft_status=not_saved`；后续收到独立的、明确的用户确认输入，才能将 19:00 写为已确认草稿。若用户未授权替代建议，则只报告冲突和等待用户选择。

## 6. 推荐项目结构

```text
README.md
.env.example
.gitignore
requirements.txt
src/
  __init__.py
  main.py
  agent.py
  llm_client.py
  mock_policy.py
  models.py
  tools.py
  storage.py
  trace.py
  policy.py
  time_utils.py
tests/
  test_tools.py
  test_policy.py
  test_idempotency.py
  test_agent_mock.py
  test_limits.py
examples/
  inputs/
    normal.json
    missing.json
    risk.json
    conflict.json
    duplicate.json
    save_failure.json
    confirmed_alternative.json
  outputs/
  traces/
  test_results.txt
data/
  materials.json
  schedule.json
  rules.json
docs/
  01-requirements.md
  02-solution.md
  03-evaluation.md
  04-ai-usage.md
  05-retrospective.md
```

## 7. 测试矩阵（全部必须验收）

| ID | 场景 | 预期 | 关键断言 |
|---|---|---|---|
| T01 | M05 无风险且时段空闲 | `completed`，草稿保存 | DB 存在一份；`published=false` |
| T02 | M02 缺少版权状态 | `needs_information` | 不得 `approved`，明确缺失字段 |
| T03 | M03 版权禁止 | `blocked` | 命中规则 ID，不写草稿 |
| T04 | M01 18:00 已占用、19:00 空闲，hard | `needs_confirmation` | 建议 19:00，未授权不能保存为已确认草稿 |
| T05 | T04 用户明确确认 19:00 | `completed` | 19:00 保存草稿，仍 `published=false` |
| T06 | T01 同请求重复执行 | 第二次 `existing` | 草稿总数不变、ID 相同 |
| T07 | 保存工具故障注入 | `save_failed` | 无假成功、无新增草稿 |
| T08 | max_steps 或工具预算耗尽 | `incomplete` | 有明确限制原因 |
| T09 | 候选时间再次冲突 | 模型继续查询或请求确认 | 不会写入冲突时段 |
| T10 | 同 request_id 不同内容 | 明确冲突 | 不覆盖旧草稿 |

测试隔离：每个测试使用临时 SQLite DB；合成数据固定；使用 pytest。Mock 测试验证代码流程，live 测试验证模型动作选择。至少 3 组真实输入、实际输出、Trace 覆盖正常、资料不足、工具失败；另保留冲突与重复提交的 Trace。至少两条 **live** Trace 显示不同观察导致不同下一动作（例如：时段空闲→保存；时段冲突→查询候选/请求确认）。如果没有 API key，必须在文档如实标明 live 验证未完成，不能将 mock Trace 标记为 live。

## 8. Trace 规范

Trace 文件必须由程序运行自动生成，字段示例：

```json
{
  "case_id": "T04",
  "mode": "live",
  "model": "configured-model-name",
  "started_at": "<actual timestamp>",
  "steps": [
    {
      "step": 1,
      "action": "query_slots",
      "arguments": {"platform": "short_video", "requested_time": "2026-11-03T18:00:00+08:00"},
      "observation_summary": {"available": false, "alternatives": ["2026-11-03T19:00:00+08:00"]},
      "next_action": "request_confirmation",
      "decision_basis": "Requested slot occupied; alternative needs explicit approval"
    }
  ],
  "final_status": "needs_confirmation",
  "published": false
}
```

上面只是结构示意，**不得将其直接当成真实执行日志**。真实运行中 `next_action` 应来自下一轮模型实际返回，而不是预填。日志不得记录密钥、个人信息或模型隐藏推理。

## 9. 文档和 README 要求

- `README.md`：Python 版本、安装命令、环境变量、mock/live CLI、运行 pytest、示例输入输出、Trace 查看方式、评审入口、已知限制。
- `docs/01-requirements.md`：用户画像、业务流程、输入输出、六项验收、成功标准、非目标。
- `docs/02-solution.md`：架构图（可用 Mermaid）、Agent Loop、工具契约、确定性规则与 LLM 职责边界、确认权限、时段冲突、幂等事务、错误恢复、技术取舍。
- `docs/03-evaluation.md`：逐个测试预期和实际结果，引用 `examples/` 文件，注明运行模式和模型；失败及限制不能隐藏。
- `docs/04-ai-usage.md`：真实记录 Codex/其他 AI 辅助范围、用户本人实际做的需求取舍/代码修改/验证，不要代替用户捏造个人贡献；未确定部分留 `TODO: candidate fill in`。
- `docs/05-retrospective.md`：技术难点、学到的内容、下一步；未经用户确认的主观经历留待本人填写。
- `.env.example` 只含变量名及虚构占位符；`.gitignore` 排除 `.env`, `*.sqlite`, 缓存、临时日志、私密输出。

## 10. Codex 实施顺序

1. 初始化目录、数据、Pydantic/数据模型、CLI 入口和依赖。
2. 实现确定性规则检查、时间冲突检查、SQLite 幂等保存与故障注入，先写/跑工具测试。
3. 实现真实 LLM 客户端及 Agent Loop，工具 schema、工具反馈、步数上限、Trace；单独实现明确标识的 mock 策略。
4. 实现输出状态的服务端核验，尤其禁止未确认硬性时间更改、硬阻断保存、虚报发布/保存。
5. 编写并运行 T01–T10；修复失败，保存真实测试输出。
6. 有真实模型凭据时运行 live 代表性场景并保存两条差异路径；否则保留 live 运行命令，文档如实标注未验证。
7. 补充 README、五份文档、运行时长与已知限制；检查无密钥；提供 `git status` 和 `git rev-parse HEAD`，由用户决定是否提交/推送。

## 11. 完成定义（Definition of Done）

- [ ] CLI 可复制运行，mock 不需要密钥；live 接口确实调用模型。
- [ ] 真实 LLM 至少一次“选择动作→工具执行→观察→后续决策/结束”循环；如未能运行则如实标注。
- [ ] 六项强制验收覆盖，并有自动化测试。
- [ ] 至少三组实际输入、输出和自动生成 Trace；正常、资料不足、工具失败均覆盖。
- [ ] 至少两条不同工具结果下的 **真实模型** 动态决策 Trace；若缺失明确列为未完成。
- [ ] 硬性时间变更必须用户明确确认；风险阻断不可绕过。
- [ ] 同请求重复保存幂等，保存失败如实报告。
- [ ] 执行上限生效，返回 `incomplete`。
- [ ] 任何输出都不声称已发布；仅本地草稿。
- [ ] README、docs/ 五份文档、tests/、examples/、data/、依赖和 `.env.example` 齐全。
- [ ] 不包含真实 API key、隐私数据、伪造 Trace 或未经验证的成功宣称。

## 12. 需要候选人亲自确认的事项

- 最终使用哪个模型/服务及实际费用与运行可用性。
- 规则风险中哪些属于硬阻断、哪些属于人工复核（本手册建议用合成规则，需在 README 说明假设）。
- 对“待确认提案”是否持久化：默认不保存排期草稿，只返回建议；如果改为保存提案，必须保证不占位、不标记已确认。
- `04-ai-usage.md` 中真实个人贡献、修改记录、实际投入时间；`05-retrospective.md` 中真实反思。
- 最终 GitHub URL、提交 SHA、评审权限与提交操作。
