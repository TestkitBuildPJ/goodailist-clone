"""Structured logging helper (PR2).

Enterprise observability entrypoint cho VibecodeKit.  Mục tiêu:

* Thay cho ``print()`` ad-hoc rải rác module (CLI ``print()`` giữ nguyên —
  contract user-facing stdout / JSON pipe của ``python -m vibecodekit.*``).
* Cho phép deployment route log sang syslog / JSON observability backend
  thuần stdlib — không thêm dependency mới (invariant Python-pure).

Public API:

``get_logger(name) -> logging.Logger``
    Singleton wrapper quanh ``logging.getLogger(name)``.  Lần gọi đầu
    tiên trong process khởi tạo handler ``StreamHandler(sys.stderr)``
    với formatter đã chọn theo env.  Các lần gọi sau trả logger có
    sẵn; handler chỉ được add một lần duy nhất cho từng logger.

Env switches:

* ``VIBECODE_LOG_LEVEL`` (default ``INFO``) — ``DEBUG`` / ``INFO`` /
  ``WARNING`` / ``ERROR`` / ``CRITICAL``.  Giá trị không hợp lệ fall
  back về ``INFO``.
* ``VIBECODE_LOG_JSON`` (default unset / ``0``) — khi ``=1`` xuất mỗi
  record dưới dạng JSON 1-line ``{"ts","level","name","msg",...}``.
  Tiện ``2>&1 | jq`` cho enterprise log pipeline.

Invariants:

* ``logger.propagate = False`` — tránh bão log khi downstream cấu hình
  root logger riêng (ELK handler, Sentry, v.v.).
* JSON formatter chỉ dùng ``json.dumps`` (stdlib) — không import
  ``structlog`` / ``python-json-logger``.
* ``print()`` trong ``_main()`` / ``if __name__ == "__main__"`` KHÔNG
  đổi — đó là contract stdout của CLI.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

_DEFAULT_LEVEL = "INFO"
_CONFIGURED: dict[str, bool] = {}


class _JsonFormatter(logging.Formatter):
    """Format log record thành JSON 1-line (stdlib-only).

    Field ổn định: ``ts`` (ISO-8601 tương đương ``%(asctime)s``),
    ``level``, ``name``, ``msg``.  Mọi ``extra={}`` do call site
    truyền vào được merge vào top-level object miễn không đụng key
    bảo lưu.
    """

    _RESERVED = frozenset(
        {
            "args",
            "asctime",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "message",
            "module",
            "msecs",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "thread",
            "threadName",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "name": record.name,
            "msg": record.getMessage(),
        }
        # Merge any structured extras attached to the record.
        for key, value in record.__dict__.items():
            if key in self._RESERVED or key.startswith("_"):
                continue
            try:
                json.dumps(value)  # skip non-serialisable
            except (TypeError, ValueError):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _resolve_level() -> int:
    raw = os.environ.get("VIBECODE_LOG_LEVEL", _DEFAULT_LEVEL).upper().strip()
    level = getattr(logging, raw, None)
    if not isinstance(level, int):
        level = logging.INFO
    return level


def _build_handler() -> logging.Handler:
    handler = logging.StreamHandler(sys.stderr)
    if os.environ.get("VIBECODE_LOG_JSON", "0") == "1":
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s: %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )
    return handler


def get_logger(name: str) -> logging.Logger:
    """Trả về logger đã cấu hình theo env.

    Gọi nhiều lần với cùng ``name`` luôn trả cùng instance (đặc tính
    của ``logging.getLogger``) và handler chỉ add một lần nhờ
    ``_CONFIGURED`` guard.
    """
    logger = logging.getLogger(name)
    if _CONFIGURED.get(name):
        return logger
    logger.setLevel(_resolve_level())
    # Avoid duplicate handlers if caller already attached one.
    if not logger.handlers:
        logger.addHandler(_build_handler())
    logger.propagate = False
    _CONFIGURED[name] = True
    return logger


def reset_for_tests() -> None:
    """Xoá cache cấu hình để test có thể re-init logger theo env mới.

    Chỉ dành cho test suite; không export qua ``__all__``.
    """
    _CONFIGURED.clear()
    # Remove our handlers from known loggers to prevent bleed between
    # tests.  Chúng ta chỉ đụng logger thuộc namespace ``vibecodekit``.
    for name in list(logging.root.manager.loggerDict):
        if name == "vibecodekit" or name.startswith("vibecodekit."):
            lg = logging.getLogger(name)
            for h in list(lg.handlers):
                lg.removeHandler(h)


__all__ = ["get_logger"]
