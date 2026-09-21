# 文件：docs/plugins.md
# Plugins

mini-harness 插件是一个**只实现 `register(app)` 的普通对象**，不需要继承基类，也不需要注册元数据。

## Contract

```python
from harness import HarnessApp


class GreetingPlugin:
    name = "greeting"

    def register(self, app: HarnessApp) -> None:
        @app.tool
        def greet(name: str) -> str:
            """向指定名字打招呼。"""
            return f"你好，{name}！"
```

两个约定：

- `name: str` — 插件标识，用于日志与 `mini-harness plugins` 输出
- `register(app)` — 唯一的扩展点，可以注册 Tool、Middleware

`register` 在 `app.build()` 之前被调用；在 `build()` 之后再注册会抛 `RuntimeError`。

## Explicit plugin registration

```python
from harness import HarnessApp
from my_package.plugin import GreetingPlugin

app = HarnessApp()
app.use(GreetingPlugin())
```

推荐方式。安装一个包与执行它的代码是两件事，显式注册把两者分开。

## Installed package discovery

插件包通过 PyPA Entry Points 声明自己：

```toml
# plugin-project/pyproject.toml
[project]
name = "my-harness-plugin"
dependencies = ["mini-harness>=0.12"]

[project.entry-points."mini_harness.plugins"]
greeting = "my_package.plugin:GreetingPlugin"
```

宿主项目启用自动发现：

```toml
# harness.toml
[plugins]
auto_discover = true
names = []          # 留空 = 全部；填写则只加载列出的 Entry Point 名
```

只加载指定插件：

```toml
[plugins]
auto_discover = true
names = ["greeting"]
```

也可以只发现但不自动启用：

```python
app.discover_plugins(names=("greeting",))
```

查看当前已安装的插件：

```bash
mini-harness plugins
```

## Security note

`auto_discover = true` 意味着**导入即执行**已安装第三方包的 `register()`。这是有意的默认关闭项：

- 供应链风险：一个被投毒的依赖可以在导入时做任何事
- 复现性：运行用到哪些能力应当由项目显式声明

如果确实需要自动发现，建议配合锁定依赖版本与私有索引。

## Testing a plugin

`register()` 之后可以直接断言注册结果，不需要启动 Runtime：

```python
def test_plugin_registers_tool() -> None:
    app = HarnessApp()

    class MathPlugin:
        name = "math"

        def register(self, target: HarnessApp) -> None:
            @target.tool(name="plugin_add")
            def add(a: int, b: int) -> int:
                return a + b

    app.use(MathPlugin())
    assert [item.name for item in app._tools] == ["plugin_add"]
```

`tests/test_app_config_plugins.py` 里的 `test_explicit_plugin_registration_is_one_method` 就是这个模式。
