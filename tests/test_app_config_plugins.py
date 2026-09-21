# 文件：tests/test_app_config_plugins.py
from harness import HarnessApp
from harness.app.config import load_config
from harness.app.errors import UnsafeServerConfigurationError
from harness.app.server import validate_local_bind


def test_toml_config_expands_environment(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TEST_MODEL", "example-model")
    path = tmp_path / "harness.toml"
    path.write_text(
        """
[app]
model = "${TEST_MODEL}"
database_path = "data/test.db"

[rag]
enabled = true
collection_name = "docs"

[mcp]
enabled = true
[[mcp.servers]]
name = "demo"
transport = "http"
url = "http://localhost:9000/mcp"
allowed_tools = ["multiply"]
""".strip(),
        encoding="utf-8",
    )
    config = load_config(path)
    assert config.app.model == "example-model"
    assert config.rag.enabled is True
    assert config.mcp.servers[0].allowed_tools == ("multiply",)


def test_missing_toml_is_valid_zero_config(tmp_path) -> None:
    config = load_config(tmp_path / "missing.toml", optional=True)
    assert config.security.enabled is True
    assert config.rag.enabled is False
    assert config.plugins.auto_discover is False


def test_explicit_plugin_registration_is_one_method() -> None:
    app = HarnessApp()

    class MathPlugin:
        name = "math"

        def register(self, target: HarnessApp) -> None:
            @target.tool(name="plugin_add")
            def add(a: int, b: int) -> int:
                return a + b

    app.use(MathPlugin())
    assert [item.name for item in app._tools] == ["plugin_add"]


def test_local_unauthenticated_server_refuses_public_bind() -> None:
    try:
        validate_local_bind("0.0.0.0", allow_unsafe_public_no_auth=False)
    except UnsafeServerConfigurationError:
        pass
    else:
        raise AssertionError("public unauthenticated bind must be rejected")

    validate_local_bind("127.0.0.1", allow_unsafe_public_no_auth=False)
