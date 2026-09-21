# 文件：tests/__init__.py
# 把 tests 显式声明为常规包（而不是依赖 PEP 420 命名空间包）：
# 多个测试用 `from tests.fakes_security import ...` 这类导入，而命名空间包会被
# site-packages 里同名的顶层 `tests` 包抢先解析。本目录已被 pyproject.toml 的
# packages.find.exclude 排除，不会进入发行版。
