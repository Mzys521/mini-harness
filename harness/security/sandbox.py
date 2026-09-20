# 文件：harness/security/sandbox.py
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class SandboxResult:
    return_code: int | None
    stdout: str
    stderr: str
    timed_out: bool = False

class SandboxPolicyError(PermissionError):
    pass

class ProcessIsolationSandbox:
    """Phase 9 的可替换 Process Isolation Adapter。

    重要：subprocess + 临时目录不是强 OS Security Sandbox。
    它只提供 shell=False、可执行文件 allowlist、最小环境变量、超时与输出上限。
    真正不可信代码执行应替换为 Container/VM/AppContainer 等强隔离实现。
    """

    def __init__(
        self,
        *,
        allowed_executables: frozenset[str],
        timeout_seconds: float = 3.0,
        max_output_chars: int = 8_000,
        env_allowlist: frozenset[str] = frozenset(),
    ) -> None:
        self.allowed_executables = {
            Path(item).name.casefold()
            for item in allowed_executables
        }
        self.timeout_seconds = timeout_seconds
        self.max_output_chars = max_output_chars
        self.env_allowlist = env_allowlist

    def run(
        self,
        command: list[str],
    ) -> SandboxResult:
        if not command:
            raise ValueError(
                "command cannot be empty"
            )

        executable_name = (
            Path(command[0]).name.casefold()
        )
        if (
            executable_name
            not in self.allowed_executables
        ):
            raise SandboxPolicyError(
                f"executable not allowed: {executable_name}"
            )

        environment = {
            key: os.environ[key]
            for key in self.env_allowlist
            if key in os.environ
        }
        # 减少 Python 从用户 site-packages 自动加载环境内容。
        environment["PYTHONNOUSERSITE"] = "1"

        with tempfile.TemporaryDirectory(
            prefix="mini_harness_sandbox_"
        ) as working_directory:
            try:
                completed = subprocess.run(
                    command,
                    shell=False,
                    cwd=working_directory,
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                return SandboxResult(
                    return_code=None,
                    stdout=self._truncate(
                        exc.stdout or ""
                    ),
                    stderr=self._truncate(
                        exc.stderr or ""
                    ),
                    timed_out=True,
                )

        return SandboxResult(
            return_code=(
                completed.returncode
            ),
            stdout=self._truncate(
                completed.stdout
            ),
            stderr=self._truncate(
                completed.stderr
            ),
            timed_out=False,
        )

    def _truncate(
        self,
        value: str,
    ) -> str:
        if (
            len(value)
            <= self.max_output_chars
        ):
            return value

        return (
            value[
                : self.max_output_chars
            ]
            + "\n[TRUNCATED_BY_SANDBOX_POLICY]"
        )
