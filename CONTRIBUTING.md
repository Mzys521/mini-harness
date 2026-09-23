# 文件：CONTRIBUTING.md
# Contributing

感谢你对 mini-harness 的关注！本文档说明开发环境搭建、设计规则与协作流程。

## Development setup

- Python 3.12+（Core 支持 3.11，但 `[rag]` / `[mcp]` 两条 Extra 依赖 `chromadb>=1.0` 与 `mcp>=2`，实际需要 3.12+）
- 安装（含开发依赖）：

```bash
pip install -e ".[server,dev]"
```

- 参考 `.env.example` 配置 `.env`（**只有凭据、Pepper 与 `HARNESS_APP` 会被直接读取**；其余设置写在 `harness.toml`，需要随环境变化时用 `${VAR}` 展开——见 `docs/architecture.md` 的 Configuration source of truth）
- 确认环境就绪：

```bash
python -m compileall -q harness tests
pytest -q                    # 与 CI 完全一致的调用方式
mini-harness doctor          # 不调用模型，只检查配置与可选依赖
```

> 请用 `pytest`（控制台脚本）而不是 `python -m pytest`：后者会把当前目录塞进 `sys.path`，从而掩盖 `tests` / `app_tools` 的导入问题——CI 跑的正是 `pytest -q`。`pyproject.toml` 里的 `pythonpath = ["."]` 已经保证两者行为一致，但按 CI 的方式跑才是有意义的验证。

- 改动前端时（源码在 `frontend/`，构建产物 `harness/ui/static/` 入库）：

```bash
cd frontend
npm install
npm run test                 # vitest + jsdom
npm run build                # vue-tsc --noEmit + vite build → harness/ui/static/
```

> 提交前请确保 `harness/ui/static/` 与 `frontend/src/` 同步：构建产物是运行时真正加载的文件，只改源码不重新构建等于没有生效。

### 前端导航改动检查

- 指标栏需覆盖显示开关、SSE 重放幂等、历史回放一致性、缓存缺失/零值、空会话和临时会话清理；人工检查桌面单行及窄屏换行。不可用数字显示 `—`，上下文估算显示 `≈`。精确 token 后续开发按 `docs/token-accounting-plan.md` 验收。

- 设置需验证浮窗左侧分类、使用习惯读取/保存与失败保护、旧 `#/preferences` 链接、切换分类保留编辑内容，以及打开设置不丢失聊天草稿。
- 配色需验证六位 HEX 校验、浏览器持久化、自定义开关与恢复主题颜色；在窄屏检查设置内容滚动和关闭入口。
- 对话定位需检查悬浮摘要、点击滚动、当前轮次高亮、空会话清理、长会话及窗口大小变化；点击历史定位不能被自动跟随拉回，键盘和减少动画偏好继续有效。

- 入口为 `App.vue`，Hash 地址逻辑在 `useWorkbenchRoute.ts`；项目树为 `ProjectTree.vue`、普通列表为 `ChatList.vue`、管理页为 `CapabilityPage.vue` / `PersonalPage.vue`。
- 项目文件夹复用 Workspace；普通会话用 `desktop_chats` 元数据表，不改旧工作区会话外键、不创建磁盘聊天目录。
- 导航测试应覆盖直接地址、刷新/历史切换、工作区与会话匹配、归档/删除目标项目，以及辅助页面期间草稿与 SSE 保留。
- 验证 RAG 创建上传、SKILL.md 导入、任务时间含时区、技能选择、普通会话无需工作区；MCP/RAG 的 503/404 与失败重试需保留，PR 仍说明未接入。
- 临时对话必须测试数据库/审计零新增、内置 Provider 不留响应缓存、断开取消和 TTL；页面离开/刷新不保留草稿或正文。定时任务测试审批前不创建、原子 claim、重复任务合并补跑与暂停。
- 人工检查深色/浅色/纸张主题、窄屏、隐藏边界拖动和聊天滚动条；不要用真实用户会话做写入测试。

## Design rules

1. **内部复杂，外部简单。** 新增子系统放在 `harness/<subsystem>/`，由 `harness/app/assembly.py` 组装；不要把它加进开发者必须手工初始化的清单。
2. **Public API 只增不破。** `harness/__init__.py` 的导出是稳定契约；其余路径视为 Internal API，变更时请在 CHANGELOG 说明。
3. **可选依赖必须 Lazy Import。** Core 只允许依赖 `openai` / `pydantic` / `python-dotenv` / `jsonschema` / `opentelemetry-api`。新的可选能力走 Extras，并在导入失败时抛 `FeatureDependencyError`，附上可执行的安装命令。
4. **Tool 注册在 build 之前完成。** 不要为运行期动态注册开后门；可复现性优先于便利。
5. **不可信数据不提升为指令。** Tool Result / Retrieval Result / MCP Resource 一律当作数据，放进带标注的分区。
6. **副作用必须可对账。** 非幂等操作按 `STARTED` / `COMPLETED` / `UNCERTAIN` 三态记录，宁可进入 `WAITING_RECONCILIATION`，不要盲目重试。

## Adding a Tool

推荐函数式写法（`@app.tool` 保留原函数，因此可以直接单元测试）：

```python
from harness import HarnessApp

app = HarnessApp()


@app.tool(permissions=("note.create",), side_effect=True)
def create_note(title: str, body: str) -> dict:
    """创建一条笔记。"""
    return {"created": True, "title": title, "body": body}
```

需要更细的 Schema 控制时，仍可用 `tool_from_pydantic` 工厂构建旧式 `Tool`——两者可以混用。项目示例工具放在 `app_tools/`。

## Style

- 遵循仓库现有风格：类型标注、frozen dataclass、简洁中文注释
- 行宽 100，`ruff` 为唯一 lint 标准；存量的 `api.py` 里 FastAPI `Depends` 默认参数告警是既有状态，不要顺手大改
- 新增能力如需观测：通过构造函数注入 `Observability` / `Metrics`，在业务外层包裹 `span` 并记录指标，未接入时保持可选
- 测试放在 `tests/` 下，文件命名 `test_*.py`
- 不要提交 `.env`、`data/`、`del/`、缓存与构建产物（已在 `.gitignore` 中排除）

## Pull requests

1. Fork 并克隆仓库
2. 从 `main` 拉出分支：`feat/phase13-xxx`、`fix/tool-timeout`、`docs/update-readme`
3. 确保 `python -m compileall -q harness tests` 与 `pytest -q` 均通过
4. 使用 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/)：`feat:` / `fix:` / `docs:` / `test:` / `refactor:` / `chore:`
5. PR 描述里说明：变更动机、实现方案、验证方式

## Stage conventions

项目按 14 个阶段推进（见 README 路线图，Phase 1–14 已完成）。每完成一个阶段请同步：

1. 新增或更新测试，保持 `pytest` 全量通过
2. 更新 README 的「路线图」与「已实现能力」
3. 在 [CHANGELOG.md](CHANGELOG.md) 记录变更（开发中写进 `[Unreleased]`）
4. 里程碑达成后打标签：`git tag -a v0.x.0 -m "v0.x.0 — Phase x 完成"`

### 版本号与发布

运行时的版本号**只有一个来源**：`harness/__init__.py` 的 `__version__`（FastAPI 的 `version`、`GET /healthz` 与 `ObservabilityConfig.service_version` 都读它）。发版时需要同步四处：

| 位置 | 说明 |
| --- | --- |
| `pyproject.toml` → `[project].version` | 分发包版本，必须与 `__version__` 一致 |
| `harness/__init__.py` → `__version__` | 运行时唯一来源 |
| `frontend/package.json` → `version`（以及 `package-lock.json` 的两处） | 工作台前端包版本，跟随框架版本 |
| `README.md` | Version 徽章、阶段数（「Phase 1–N」）与路线图状态 |

发布流程：

1. 把 CHANGELOG 的 `## [Unreleased]` 改为 `## [x.y.z] - YYYY-MM-DD`，并补一行 `> 主题：…` 摘要；在其上方保留空的 `## [Unreleased]`
2. 更新上表四处版本号，并同步 `AGENT.md` / `HANDOFF.md` 的阶段状态
3. 打标签并推送：`git tag -a vx.y.z -m "vx.y.z — Phase x 完成"` → `git push origin main --follow-tags`

> 版本语义：README 的规则是**旧能力 + 新能力 = 新版本**。新增能力走 minor（`0.13.0` → `0.14.0`）；记录在 CHANGELOG「兼容」一节的行为变化若影响既有调用方，提交信息用 `feat!:`。

## Reporting issues

- 缺陷报告请包含：复现步骤、期望行为、实际行为、运行环境（Python 版本 / 操作系统 / 是否启用可选 Extras）
- 安全问题请走 [SECURITY.md](SECURITY.md)，不要开公开 Issue
