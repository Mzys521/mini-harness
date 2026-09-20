# 文件：tests/test_sandbox.py
import sys

import pytest

from harness.security.sandbox import (
    ProcessIsolationSandbox,
    SandboxPolicyError,
)

def test_process_isolation_sandbox_allows_explicit_executable() -> None:
    sandbox = ProcessIsolationSandbox(
        allowed_executables=frozenset({
            sys.executable
        }),
        timeout_seconds=2.0,
    )

    result = sandbox.run([
        sys.executable,
        "-c",
        "print(2 + 3)",
    ])

    assert result.return_code == 0
    assert result.stdout.strip() == "5"
    assert result.timed_out is False

def test_process_isolation_sandbox_denies_unknown_executable() -> None:
    sandbox = ProcessIsolationSandbox(
        allowed_executables=frozenset({
            sys.executable
        })
    )

    with pytest.raises(
        SandboxPolicyError
    ):
        sandbox.run([
            "definitely-not-allowed",
            "--version",
        ])
