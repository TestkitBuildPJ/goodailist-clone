"""Playwright lifecycle manager — invoked by the FastAPI daemon.

This module imports ``playwright.sync_api`` at import time and is therefore
**only safe to import when the ``[browser]`` extras are installed**.  The
package's ``__init__`` deliberately excludes it from the eager import
list so unit tests can still load the rest of the browser package
without those dependencies.

A single ``BrowserManager`` instance owns:

- one Chromium :class:`Browser` (launched once, reused).
- a lazily-created :class:`BrowserContext` per "tab" (so cookies /
  localStorage persist between commands until ``new_tab`` reset).
- in-memory ring buffers for ``console`` and ``network`` events.

The manager is intentionally thin — most logic lives in
:mod:`commands_read` and :mod:`commands_write`, which call into
``run_read_verb`` / ``run_write_verb`` here.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:  # pragma: no cover — exercised only with [browser] extras installed.
    from playwright.sync_api import (  # type: ignore[import-not-found]
        Browser,
        BrowserContext,
        Page,
        Playwright,
        sync_playwright,
    )
except ModuleNotFoundError as e:  # pragma: no cover
    raise ModuleNotFoundError(
        "vibecodekit.browser.manager requires the [browser] extras. "
        "Install with: pip install 'vibecodekit-hybrid-ultra[browser]' "
        "&& playwright install chromium"
    ) from e

from . import snapshot as snap_mod

# Ring-buffer caps — enough to be useful, small enough to keep memory bounded.
CONSOLE_BUFFER: int = 200
NETWORK_BUFFER: int = 200


@dataclass
class TabState:
    page: Page
    context: BrowserContext
    console: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=CONSOLE_BUFFER))
    network: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=NETWORK_BUFFER))


class BrowserManager:
    """Owns the playwright instance and a dict of tabs."""

    def __init__(self, headless: bool = True):
        self._lock = threading.Lock()
        self.headless = headless
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._tabs: dict[str, TabState] = {}
        self._active_tab: str = "default"
        self._last_activity_ts: float = time.time()

    # ---- lifecycle -------------------------------------------------------

    def start(self) -> None:
        with self._lock:
            if self._browser is not None:
                return
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=self.headless)
            self._open_tab(self._active_tab)
            self._touch()

    def stop(self) -> None:
        with self._lock:
            for tab in self._tabs.values():
                with _safe():
                    tab.context.close()
            self._tabs.clear()
            if self._browser is not None:
                with _safe():
                    self._browser.close()
                self._browser = None
            if self._pw is not None:
                with _safe():
                    self._pw.stop()
                self._pw = None

    @property
    def last_activity_ts(self) -> float:
        return self._last_activity_ts

    def _touch(self) -> None:
        self._last_activity_ts = time.time()

    # ---- tabs ------------------------------------------------------------

    def _open_tab(self, name: str) -> TabState:
        if self._browser is None:
            raise RuntimeError("browser not started")
        ctx = self._browser.new_context()
        page = ctx.new_page()

        tab = TabState(page=page, context=ctx)

        def _on_console(msg):  # pragma: no cover — playwright callback
            tab.console.append({"type": msg.type, "text": msg.text, "ts": time.time()})

        def _on_request(req):  # pragma: no cover
            tab.network.append(
                {
                    "method": req.method,
                    "url": req.url,
                    "kind": "request",
                    "ts": time.time(),
                }
            )

        def _on_response(resp):  # pragma: no cover
            tab.network.append(
                {
                    "method": resp.request.method,
                    "url": resp.url,
                    "status": resp.status,
                    "kind": "response",
                    "ts": time.time(),
                }
            )

        page.on("console", _on_console)
        page.on("request", _on_request)
        page.on("response", _on_response)

        self._tabs[name] = tab
        return tab

    def _tab(self, name: str | None = None) -> TabState:
        n = name or self._active_tab
        if n not in self._tabs:
            self._open_tab(n)
        return self._tabs[n]

    # ---- read verbs ------------------------------------------------------

    def run_read_verb(self, verb: str, target: str | None, extras: dict[str, Any]) -> Any:
        self._touch()
        tab = self._tab(extras.get("tab"))
        page = tab.page

        if verb == "text":
            return page.evaluate("() => document.body && document.body.innerText || ''")
        if verb == "html":
            return page.content()
        if verb == "links":
            return page.evaluate(
                "() => Array.from(document.querySelectorAll('a[href]'))"
                ".slice(0, 200).map(a => ({href: a.href, text: (a.innerText||'').trim()}))"
            )
        if verb == "forms":
            return page.evaluate(
                "() => Array.from(document.querySelectorAll('form'))"
                ".map(f => ({action: f.action, method: f.method, "
                "fields: Array.from(f.elements).map(e => ({name: e.name, type: e.type}))}))"
            )
        if verb == "aria":
            return page.accessibility.snapshot(interesting_only=True) or {}
        if verb == "console":
            return list(tab.console)
        if verb == "network":
            return list(tab.network)
        if verb == "snapshot":
            return self._capture_snapshot(tab)
        if verb == "tabs":
            return sorted(self._tabs.keys())
        if verb == "status":
            return {
                "tabs": sorted(self._tabs.keys()),
                "active": self._active_tab,
                "last_activity_ts": self._last_activity_ts,
            }
        raise ValueError(f"unknown read verb: {verb}")

    def _capture_snapshot(self, tab: TabState) -> snap_mod.Snapshot:
        page = tab.page
        text = page.evaluate("() => document.body && document.body.innerText || ''")
        url = page.url
        title = page.title()
        aria = page.accessibility.snapshot(interesting_only=True) or {}
        norm_aria = snap_mod.normalise_aria(aria)
        return snap_mod.Snapshot(
            url=url,
            title=title,
            aria=[norm_aria] if norm_aria else [],
            text=text,
            dom_hash=snap_mod.hash_dom({"url": url, "title": title, "aria": norm_aria}),
            console=list(tab.console),
            network=list(tab.network),
        )

    # ---- write verbs -----------------------------------------------------

    def run_write_verb(self, verb: str, target: str | None, extras: dict[str, Any]) -> Any:
        self._touch()
        tab = self._tab(extras.get("tab"))
        page = tab.page

        if verb == "goto":
            assert target, "goto requires a URL"
            wait_until = extras.get("wait_until", "load")
            page.goto(target, wait_until=wait_until)
            return {"url": page.url, "title": page.title()}
        if verb == "click":
            selector = extras.get("selector") or target
            page.click(str(selector))
            return {"clicked": selector}
        if verb == "fill":
            selector = extras.get("selector") or target
            value = extras.get("value", "")
            page.fill(str(selector), str(value))
            return {"filled": selector}
        if verb == "select":
            selector = extras.get("selector") or target
            value = extras.get("value")
            page.select_option(str(selector), value)
            return {"selected": selector, "value": value}
        if verb == "scroll":
            x = int(extras.get("x", 0))
            y = int(extras.get("y", 600))
            page.evaluate(f"() => window.scrollTo({x}, {y})")
            return {"scrolled_to": [x, y]}
        if verb == "wait_for":
            selector = extras.get("selector") or target
            timeout = float(extras.get("timeout", 5_000))
            page.wait_for_selector(str(selector), timeout=timeout)
            return {"waited_for": selector}
        if verb == "screenshot":
            path = extras.get("path") or str(Path.cwd() / "vck-screenshot.png")
            page.screenshot(path=path, full_page=bool(extras.get("full_page", True)))
            return {"path": path}
        if verb == "set_cookie":
            cookie = dict(extras)
            tab.context.add_cookies([cookie])  # type: ignore[arg-type]
            return {"set": cookie.get("name")}
        if verb == "new_tab":
            name = str(extras.get("name") or target or f"tab-{len(self._tabs)}")
            self._open_tab(name)
            self._active_tab = name
            return {"opened": name}
        if verb == "close_tab":
            name = str(extras.get("name") or target or self._active_tab)
            t = self._tabs.pop(name, None)
            if t is not None:
                with _safe():
                    t.context.close()
            return {"closed": name}
        raise ValueError(f"unknown write verb: {verb}")


# Module-level singleton — created lazily on first use.  The FastAPI
# server in :mod:`server` constructs/exposes this singleton through
# dependency injection so tests can swap it out.

_singleton: BrowserManager | None = None
_singleton_lock = threading.Lock()


def get_manager(*, headless: bool = True) -> BrowserManager:
    """Return the process-wide manager, starting it if necessary."""
    global _singleton
    if _singleton is None:
        with _singleton_lock:
            if _singleton is None:
                m = BrowserManager(headless=headless)
                m.start()
                _singleton = m
    return _singleton


def stop_manager() -> None:
    global _singleton
    with _singleton_lock:
        if _singleton is not None:
            _singleton.stop()
            _singleton = None


def run_read_verb(verb: str, target: str | None, extras: dict[str, Any]) -> Any:
    return get_manager().run_read_verb(verb, target, extras)


def run_write_verb(verb: str, target: str | None, extras: dict[str, Any]) -> Any:
    return get_manager().run_write_verb(verb, target, extras)


# ---- helpers -------------------------------------------------------------


class _safe:
    """Context manager that swallows exceptions during teardown.

    Used so that an error closing one Playwright context does not leak
    and prevent us from cleaning up the rest.
    """

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # pragma: no cover
        return True


__all__ = [
    "BrowserManager",
    "TabState",
    "CONSOLE_BUFFER",
    "NETWORK_BUFFER",
    "get_manager",
    "stop_manager",
    "run_read_verb",
    "run_write_verb",
]
