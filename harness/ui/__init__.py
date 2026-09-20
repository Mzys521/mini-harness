"""The bundled mini-harness workspace.

`static/` holds the **built** Vue 3 + TypeScript frontend, committed so the
workspace runs without a Node toolchain. Edit the sources in `frontend/` and run
`npm run build` there; never hand-edit `static/`.
"""

from pathlib import Path

STATIC_DIRECTORY = Path(__file__).with_name("static")
