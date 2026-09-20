# 文件：scripts/security_smoke_test.py
import asyncio

from main import (
    run_security_check,
)

if __name__ == "__main__":
    asyncio.run(
        run_security_check()
    )