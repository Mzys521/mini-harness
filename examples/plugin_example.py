# 文件：examples/plugin_example.py
from harness import HarnessApp


class GreetingPlugin:
    name = "greeting"

    def register(self, app: HarnessApp) -> None:
        @app.tool
        def greet(name: str) -> str:
            """向指定名字打招呼。"""
            return f"你好，{name}！"


app = HarnessApp()
app.use(GreetingPlugin())


if __name__ == "__main__":
    app.cli()
