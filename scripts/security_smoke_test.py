# 文件：scripts/security_smoke_test.py
import asyncio

from harness.app.checks import run_security_check

if __name__ == "__main__":
    asyncio.run(run_security_check())
