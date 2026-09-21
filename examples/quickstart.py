# 文件：examples/quickstart.py
from harness import HarnessApp

app = HarnessApp()


@app.tool
def add(a: float, b: float) -> float:
    """计算两个数字的加法。"""
    return a + b


if __name__ == "__main__":
    app.cli()
