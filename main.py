"""
============================================================
  FORGE MASTER UI — Entry point
  Run : python main.py
============================================================
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

# Ensure the root folder is in the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ── Logging ────────────────────────────────────────────────
#
# Every backend/ui module already does `log = logging.getLogger(__name__)`,
# but nothing was configuring the root logger — so those messages were
# silently swallowed. We install a stream handler (stderr) and a rolling
# file handler (logs/forge_master.log) on the root logger here, once,
# at process start.
#
# The FORGE_MASTER_LOG_LEVEL env var lets power users crank it up to
# DEBUG without touching the code:  set FORGE_MASTER_LOG_LEVEL=DEBUG
# ────────────────────────────────────────────────────────────

_LOG_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "forge_master.log")
_LOG_FMT  = "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s"
_LOG_DATE = "%H:%M:%S"


def _configure_logging() -> None:
    """Install stderr + rolling-file handlers on the root logger."""
    level_name = os.environ.get("FORGE_MASTER_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    # Idempotent: if someone already called basicConfig we reset cleanly
    # rather than stacking duplicate handlers.
    for h in list(root.handlers):
        root.removeHandler(h)
    root.setLevel(level)

    formatter = logging.Formatter(_LOG_FMT, datefmt=_LOG_DATE)

    stream = logging.StreamHandler(stream=sys.stderr)
    stream.setFormatter(formatter)
    root.addHandler(stream)

    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        file_h = RotatingFileHandler(
            _LOG_FILE, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
        file_h.setFormatter(formatter)
        root.addHandler(file_h)
    except Exception as e:  # pragma: no cover — log dir creation is best-effort
        # Fall back to stderr-only; no point crashing the whole app because
        # we can't write to disk.
        root.warning("Could not open log file %s: %s", _LOG_FILE, e)


def main():
    _configure_logging()
    log = logging.getLogger(__name__)

    try:
        import customtkinter  # noqa: F401
    except ImportError:
        log.error(
            "CustomTkinter is not installed. Install it with:\n"
            "    pip install -r requirements.txt"
        )
        sys.exit(1)

    log.info("Starting Forge Master UI")
    from ui.app import run
    run()


if __name__ == "__main__":
    main()
