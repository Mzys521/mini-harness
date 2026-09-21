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
python -m pytest tests -q
mini-harness doctor          # 不调用模型，只检查配置与可选依赖
```

- 改动前端时（源码在 `frontend/`，构建产物 `harness/ui/static/` 入库）：

```bash
cd frontend
npm install
npm run test                 # vitest + jsdom
npm run build                # vue-tsc --noEmit + vite build → harness/ui/static/
```

> 提交前请确保 `harness/ui/static/` 与 `frontend/src/` 同步：构建产物是运行时真正加载的文件，只改源码不重新构建等于没有生效。

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

项目按 13 个阶段推进（见 README 路线图，Phase 1–13 已完成）。每完成一个阶段请同步：

1. 新增或更新测试，保持 `pytest` 全量通过
2. 更新 README 的「路线图」与「已实现能力」
3. 在 [CHANGELOG.md](CHANGELOG.md) 记录变更（开发中写进 `[Unreleased]`）
4. 里程碑达成后打标签：`git tag -a v0.x.0 -m "v0.x.0 — Phase x 完成"`

## Reporting issues

- 缺陷报告请包含：复现步骤、期望行为、实际行为、运行环境（Python 版本 / 操作系统 / 是否启用可选 Extras）
- 安全问题请走 [SECURITY.md](SECURITY.md)，不要开公开 Issue
