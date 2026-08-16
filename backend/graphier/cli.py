"""Console entry points with a friendly engine bootstrap.

`pip install graphier` deliberately does NOT pull the extraction engine:
Semantica's own dependency list includes torch/transformers/spacy
(multi-gigabyte), while Graphier's deterministic path needs none of it.
`graphier setup` installs just the engine package itself (~no ML
downloads); the scientific deps it does use are already Graphier
dependencies.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys

MISSING_ENGINE = """\
Graphier's extraction engine isn't installed yet. One command fixes it:

    graphier setup

(This runs `pip install --no-deps semantica` — the engine package alone,
no multi-gigabyte ML downloads. For Semantica's optional ML extractors
later: `pip install semantica`.)
"""


def engine_installed() -> bool:
    return importlib.util.find_spec("semantica") is not None


def install_engine() -> int:
    return subprocess.call(
        [sys.executable, "-m", "pip", "install", "--no-deps", "semantica"]
    )


def main() -> None:
    if sys.argv[1:2] == ["setup"]:
        code = install_engine()
        if code == 0:
            print("Engine installed. Start Graphier with: graphier --demo")
        raise SystemExit(code)
    if not engine_installed():
        print(MISSING_ENGINE, file=sys.stderr)
        raise SystemExit(1)
    from .main import main as run_app

    run_app()


def mcp_main() -> None:
    if not engine_installed():
        print(MISSING_ENGINE, file=sys.stderr)
        raise SystemExit(1)
    from .mcp import main as run_mcp

    run_mcp()
