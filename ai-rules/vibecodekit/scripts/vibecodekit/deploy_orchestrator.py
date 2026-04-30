"""Deploy orchestrator (v0.11.0, Phase final — F2).

Adds a SHIP layer to VibecodeKit covering 7 deploy targets:

1. **Vercel**         — `npx vercel --prod`
2. **Docker**         — generate Dockerfile + `docker build` + tag
3. **VPS**            — `rsync` + `ssh` + systemd unit + nginx snippet
4. **Cloudflare Pages** — `wrangler pages deploy`
5. **Railway**        — `railway up`
6. **Fly.io**         — `flyctl deploy`
7. **Render**         — `git push render` (Render auto-deploys on push)

Each driver implements the same contract::

    class Driver:
        name: str
        def detect(repo_dir: Path) -> bool: ...    # auto-detect
        def preflight(repo_dir: Path) -> list[Issue]: ...
        def deploy(repo_dir: Path, opts: dict) -> DeployResult: ...
        def rollback(snapshot_id: str) -> bool: ...

State files (per repo)::

    .vibecode/deploy-target.txt    — last selected target name
    .vibecode/deploy-url.txt       — last deploy URL
    .vibecode/deploy-history.jsonl — append-only deploy log

Public API::

    from vibecodekit.deploy_orchestrator import DeployOrchestrator
    o = DeployOrchestrator(repo_dir=".")
    target = o.select_target()                # auto-detect
    issues = target.preflight(o.repo)
    result = o.run(target, opts={"prod": True})
    o.rollback(result.snapshot_id)

The drivers DO NOT actually shell out by default — they use a
``runner`` callable that defaults to ``subprocess.run`` but can be
swapped to a ``DryRunner`` for tests / dry-run.  This is what enables
the unit-test suite to validate the full happy path without network or
external CLI dependencies.
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
import subprocess
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any


def _extract_url(text: str, suffix: str) -> str | None:
    m = re.search(r"https?://[^\s]+" + re.escape(suffix) + r"[^\s]*", text)
    return m.group(0).rstrip(".,") if m else None


# ---------------------------------------------------------------------------
# Runner abstraction
# ---------------------------------------------------------------------------
@dataclasses.dataclass
class RunResult:
    cmd: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


Runner = Callable[[Iterable[str], dict[str, Any]], RunResult]


def real_runner(cmd: Iterable[str], opts: dict[str, Any]) -> RunResult:
    cmd = tuple(cmd)
    cwd = opts.get("cwd")
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=opts.get("timeout", 600),
    )
    return RunResult(cmd=cmd, returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)


@dataclasses.dataclass
class DryRunner:
    """Records every invocation without actually shelling out."""

    log: list[tuple[tuple[str, ...], dict[str, Any]]] = dataclasses.field(default_factory=list)
    response: RunResult | None = None

    def __call__(self, cmd: Iterable[str], opts: dict[str, Any]) -> RunResult:
        cmd = tuple(cmd)
        self.log.append((cmd, dict(opts)))
        if self.response is not None:
            return dataclasses.replace(self.response, cmd=cmd)
        # Default success
        return RunResult(cmd=cmd, returncode=0, stdout=f"[dry-run] {' '.join(cmd)}\n", stderr="")


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class Issue:
    severity: str  # 'error' or 'warning'
    message: str


@dataclasses.dataclass(frozen=True)
class DeployResult:
    target: str
    success: bool
    url: str | None
    snapshot_id: str
    duration_s: float
    log_excerpt: str


@dataclasses.dataclass(frozen=True)
class DetectionResult:
    """Structured outcome of ``DeployOrchestrator.detect_target()``.

    Unlike ``select_target()`` (which raises on no match), this carries
    enough context for callers to render a friendly prompt, e.g.::

        "Không auto-detect được target.  Có vẻ phù hợp: docker, vps.
         Chọn 1 trong số đó hoặc thêm `--target=<name>`."
    """

    driver: _DriverBase | None
    candidates: tuple[str, ...]  # all driver.name that matched ``detect()``
    message_vi: str
    message_en: str

    @property
    def matched(self) -> bool:
        return self.driver is not None


# ---------------------------------------------------------------------------
# Driver base
# ---------------------------------------------------------------------------
class _DriverBase:
    name: str = "base"
    detect_paths: tuple[str, ...] = ()
    detect_files: tuple[str, ...] = ()
    # v0.11.0 audit follow-up — fallback detection via package.json deps.
    # A driver that lists ``next`` here will match a Next.js scaffold even
    # when no ``next.config.*`` / ``vercel.json`` marker file is present.
    detect_package_deps: tuple[str, ...] = ()

    def __init__(self, runner: Runner = real_runner):
        self.run = runner

    @staticmethod
    def _package_deps(repo_dir: Path) -> dict[str, str]:
        """Return the union of ``dependencies`` + ``devDependencies`` from
        ``package.json``.  Empty dict on parse error or missing file."""
        pkg_path = repo_dir / "package.json"
        if not pkg_path.is_file():
            return {}
        try:
            pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        deps: dict[str, str] = {}
        for key in ("dependencies", "devDependencies", "peerDependencies"):
            deps.update(pkg.get(key) or {})
        return deps

    def detect(self, repo_dir: Path) -> bool:
        if any((repo_dir / p).exists() for p in self.detect_paths):
            return True
        if any((repo_dir / f).is_file() for f in self.detect_files):
            return True
        if self.detect_package_deps:
            deps = self._package_deps(repo_dir)
            if any(dep in deps for dep in self.detect_package_deps):
                return True
        return False

    def preflight(self, repo_dir: Path) -> list[Issue]:
        return []

    def deploy(self, repo_dir: Path, opts: dict[str, Any]) -> DeployResult:
        raise NotImplementedError

    def rollback(self, snapshot_id: str) -> bool:
        # Default: drivers without history-based rollback return False.
        return False

    # -- helpers -----------------------------------------------------------
    def _run(self, cmd: Iterable[str], cwd: Path, timeout: int = 600) -> RunResult:
        return self.run(cmd, {"cwd": str(cwd), "timeout": timeout})

    def _result(
        self, repo_dir: Path, ok: bool, url: str | None, excerpt: str, started: float
    ) -> DeployResult:
        return DeployResult(
            target=self.name,
            success=ok,
            url=url,
            snapshot_id=f"{self.name}-{int(started)}",
            duration_s=time.time() - started,
            log_excerpt=excerpt[-500:] if excerpt else "",
        )


# ---------------------------------------------------------------------------
# Drivers (one per deploy target)
# ---------------------------------------------------------------------------
class VercelDriver(_DriverBase):
    name = "vercel"
    detect_files = ("vercel.json",)
    detect_paths = ("next.config.js", "next.config.mjs", "next.config.ts")
    # v0.11.0 audit follow-up: Next.js / Nuxt / SvelteKit / Remix scaffolds
    # detected even without a config marker file (Vercel is their first-
    # class host).  Keep this list small — only frameworks whose natural
    # host is Vercel to avoid misrouting generic Node apps.
    detect_package_deps = ("next", "nuxt", "@sveltejs/kit", "@remix-run/react")

    def preflight(self, repo_dir):
        issues = []
        if not (repo_dir / "package.json").is_file():
            issues.append(Issue("error", "package.json missing"))
        return issues

    def deploy(self, repo_dir, opts):
        started = time.time()
        cmd = ["npx", "vercel"]
        if opts.get("prod"):
            cmd.append("--prod")
        cmd.extend(["--yes", "--cwd", str(repo_dir)])
        r = self._run(cmd, repo_dir)
        url = _extract_url(r.stdout, ".vercel.app")
        return self._result(
            repo_dir, r.returncode == 0, url or opts.get("url"), r.stdout + r.stderr, started
        )


class DockerDriver(_DriverBase):
    name = "docker"
    detect_files = ("Dockerfile", "docker-compose.yml", "compose.yaml")

    @staticmethod
    def _detect_stack(repo_dir):
        """Return ('nextjs'|'node'|'fastapi'|'python'|'expo'|None, info_dict).

        Uses filesystem markers (package.json deps, pyproject.toml, app.json)
        to pick the right Dockerfile template.  ``None`` means unknown — the
        driver should refuse to auto-generate in that case.
        """
        pkg_path = repo_dir / "package.json"
        pkg = {}
        if pkg_path.is_file():
            try:
                pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pkg = {}
        deps = {}
        for key in ("dependencies", "devDependencies"):
            deps.update(pkg.get(key) or {})
        if "next" in deps:
            return "nextjs", {"node": "20"}
        if "expo" in deps:
            return "expo", {"node": "20"}
        if deps and ("start" in (pkg.get("scripts") or {})):
            return "node", {"node": "20", "start_script": pkg["scripts"]["start"]}
        pyproject = repo_dir / "pyproject.toml"
        requirements = repo_dir / "requirements.txt"
        has_fastapi = False
        if pyproject.is_file():
            try:
                txt = pyproject.read_text(encoding="utf-8")
                has_fastapi = "fastapi" in txt.lower()
            except OSError:
                pass
        if requirements.is_file() and not has_fastapi:
            try:
                req = requirements.read_text(encoding="utf-8").lower()
                has_fastapi = "fastapi" in req
            except OSError:
                pass
        if has_fastapi:
            return "fastapi", {"python": "3.12"}
        if pyproject.is_file() or requirements.is_file():
            return "python", {"python": "3.12"}
        return None, {}

    _DOCKERFILE_TEMPLATES = {
        "nextjs": (
            "# Auto-generated by VibecodeKit (stack: Next.js)\n"
            "FROM node:{node}-alpine\n"
            "WORKDIR /app\n"
            "COPY package*.json ./\n"
            "RUN npm ci --omit=dev || npm install --omit=dev\n"
            "COPY . .\n"
            "RUN npm run build\n"
            "ENV NODE_ENV=production PORT=3000\n"
            "EXPOSE 3000\n"
            'CMD ["npm", "run", "start"]\n'
        ),
        "node": (
            "# Auto-generated by VibecodeKit (stack: Node.js)\n"
            "FROM node:{node}-alpine\n"
            "WORKDIR /app\n"
            "COPY package*.json ./\n"
            "RUN npm ci --omit=dev || npm install --omit=dev\n"
            "COPY . .\n"
            'CMD ["npm", "start"]\n'
        ),
        "expo": (
            "# Auto-generated by VibecodeKit (stack: Expo)\n"
            "FROM node:{node}-alpine\n"
            "WORKDIR /app\n"
            "COPY . .\n"
            "RUN npm install --omit=dev\n"
            'CMD ["npx", "expo", "start", "--web"]\n'
        ),
        "fastapi": (
            "# Auto-generated by VibecodeKit (stack: FastAPI)\n"
            "FROM python:{python}-slim\n"
            "WORKDIR /app\n"
            "COPY . .\n"
            "RUN pip install --no-cache-dir -e . "
            "|| pip install --no-cache-dir -r requirements.txt\n"
            "EXPOSE 8000\n"
            'CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]\n'
        ),
        "python": (
            "# Auto-generated by VibecodeKit (stack: Python)\n"
            "FROM python:{python}-slim\n"
            "WORKDIR /app\n"
            "COPY . .\n"
            "RUN pip install --no-cache-dir -e . "
            "|| pip install --no-cache-dir -r requirements.txt "
            "|| true\n"
            'CMD ["python", "-m", "app"]\n'
        ),
    }

    def preflight(self, repo_dir):
        if (repo_dir / "Dockerfile").is_file():
            return []
        stack, _ = self._detect_stack(repo_dir)
        if stack is None:
            return [
                Issue(
                    "error",
                    "no Dockerfile and stack not recognized — create a "
                    "Dockerfile manually or add package.json/pyproject.toml",
                )
            ]
        return [Issue("warning", f"no Dockerfile — will auto-generate for stack={stack}")]

    def deploy(self, repo_dir, opts):
        started = time.time()
        if not (repo_dir / "Dockerfile").is_file():
            stack, info = self._detect_stack(repo_dir)
            if stack is None:
                return self._result(
                    repo_dir,
                    ok=False,
                    url=None,
                    excerpt=(
                        "Docker deploy aborted: stack not recognized "
                        "(no package.json/pyproject.toml/requirements.txt). "
                        "Add a Dockerfile manually."
                    ),
                    started=started,
                )
            template = self._DOCKERFILE_TEMPLATES[stack]
            (repo_dir / "Dockerfile").write_text(
                template.format(**info),
                encoding="utf-8",
            )
        tag = opts.get("tag", f"vibecode-app:{int(started)}")
        r = self._run(["docker", "build", "-t", tag, "."], repo_dir)
        return self._result(
            repo_dir,
            r.returncode == 0,
            url=f"docker://{tag}",
            excerpt=r.stdout + r.stderr,
            started=started,
        )


class VPSDriver(_DriverBase):
    name = "vps"
    detect_files = (".vps.env", "deploy/vps.env")

    @staticmethod
    def _parse_env_file(env_file):
        """Minimal key=value parser for .vps.env.  Ignores blanks and
        comments.  Strips surrounding matching quotes from values."""
        out = {}
        try:
            text = env_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return out
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            # Allow leading ``export ``.
            if line.startswith("export "):
                line = line[len("export ") :]
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip()
            # Strip surrounding matching quotes.
            if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
                v = v[1:-1]
            # Strip trailing inline comment after value.
            if k:
                out[k] = v
        return out

    def _load_config(self, repo_dir, opts):
        """Merge .vps.env (if present) with opts overrides.  opts wins."""
        env_file = next((repo_dir / f for f in self.detect_files if (repo_dir / f).is_file()), None)
        env = self._parse_env_file(env_file) if env_file else {}
        return {
            "host": opts.get("host") or env.get("VPS_HOST", ""),
            "user": opts.get("user") or env.get("VPS_USER", ""),
            "path": opts.get("path") or env.get("VPS_PATH", ""),
            "service": (opts.get("service") or env.get("VPS_SERVICE", "vibecode-app")),
        }

    _PLACEHOLDER_VALUES = {"vps.example.com", "deploy", "/srv/app", "example.com", ""}

    def preflight(self, repo_dir):
        issues = []
        env_file = next((repo_dir / f for f in self.detect_files if (repo_dir / f).is_file()), None)
        if env_file is None:
            issues.append(Issue("error", "no .vps.env (need VPS_HOST + VPS_USER + VPS_PATH)"))
            return issues
        env = self._parse_env_file(env_file)
        missing = [k for k in ("VPS_HOST", "VPS_USER", "VPS_PATH") if not env.get(k)]
        if missing:
            issues.append(
                Issue("error", f"{env_file.name} missing required keys: {', '.join(missing)}")
            )
        # Warn on obvious placeholder values.
        for k in ("VPS_HOST", "VPS_USER", "VPS_PATH"):
            v = env.get(k, "")
            if v in self._PLACEHOLDER_VALUES:
                issues.append(
                    Issue(
                        "warning",
                        f"{k}={v!r} looks like a placeholder — update "
                        f"{env_file.name} before real deploy",
                    )
                )
        return issues

    def deploy(self, repo_dir, opts):
        started = time.time()
        cfg = self._load_config(repo_dir, opts)
        host, user, path = cfg["host"], cfg["user"], cfg["path"]
        if not host or not user or not path:
            return self._result(
                repo_dir,
                ok=False,
                url=None,
                excerpt=(
                    f"VPS deploy aborted: missing config "
                    f"(host={host!r}, user={user!r}, path={path!r}). "
                    "Provide .vps.env with VPS_HOST/VPS_USER/VPS_PATH "
                    "or pass opts={host,user,path}."
                ),
                started=started,
            )
        if host in self._PLACEHOLDER_VALUES:
            return self._result(
                repo_dir,
                ok=False,
                url=None,
                excerpt=(
                    f"VPS deploy aborted: host={host!r} is a " "placeholder value. Update .vps.env."
                ),
                started=started,
            )
        r1 = self._run(["rsync", "-az", "--delete", "./", f"{user}@{host}:{path}/"], repo_dir)
        r2 = self._run(["ssh", f"{user}@{host}", f"systemctl restart {cfg['service']}"], repo_dir)
        return self._result(
            repo_dir,
            r1.returncode == 0 and r2.returncode == 0,
            url=f"https://{host}",
            excerpt=r1.stdout + r1.stderr + r2.stdout + r2.stderr,
            started=started,
        )


class CloudflareDriver(_DriverBase):
    name = "cloudflare"
    detect_files = ("wrangler.toml", "wrangler.jsonc", "wrangler.json")
    # Audit round-5 follow-up: Workers/Pages projects often have
    # ``wrangler`` as devDep but no wrangler config until first deploy.
    # ``hono`` is the dominant Workers framework.  Keep narrow.
    detect_package_deps = ("wrangler", "@cloudflare/workers-types", "hono")

    def deploy(self, repo_dir, opts):
        started = time.time()
        proj = opts.get("project", repo_dir.name)
        cmd = ["npx", "wrangler", "pages", "deploy", str(repo_dir), "--project-name", proj]
        r = self._run(cmd, repo_dir)
        url = _extract_url(r.stdout, ".pages.dev")
        return self._result(repo_dir, r.returncode == 0, url, r.stdout + r.stderr, started)


class RailwayDriver(_DriverBase):
    name = "railway"
    detect_files = ("railway.json", "railway.toml", ".railway")

    def deploy(self, repo_dir, opts):
        started = time.time()
        r = self._run(["railway", "up", "--detach"], repo_dir)
        return self._result(
            repo_dir, r.returncode == 0, opts.get("url"), r.stdout + r.stderr, started
        )


class FlyDriver(_DriverBase):
    name = "fly"
    detect_files = ("fly.toml",)

    def preflight(self, repo_dir):
        if not (repo_dir / "fly.toml").is_file():
            return [Issue("error", "no fly.toml — run `fly launch` first")]
        return []

    def deploy(self, repo_dir, opts):
        started = time.time()
        r = self._run(["flyctl", "deploy"], repo_dir)
        url = _extract_url(r.stdout, ".fly.dev")
        return self._result(repo_dir, r.returncode == 0, url, r.stdout + r.stderr, started)


class RenderDriver(_DriverBase):
    name = "render"
    detect_files = ("render.yaml", "render.yml")

    def deploy(self, repo_dir, opts):
        started = time.time()
        # Render auto-deploys on git push to the configured branch.
        remote = opts.get("remote", "render")
        branch = opts.get("branch", "main")
        r = self._run(["git", "push", remote, branch], repo_dir)
        return self._result(
            repo_dir, r.returncode == 0, opts.get("url"), r.stdout + r.stderr, started
        )


_REGISTRY: tuple[type[_DriverBase], ...] = (
    VercelDriver,
    DockerDriver,
    VPSDriver,
    CloudflareDriver,
    RailwayDriver,
    FlyDriver,
    RenderDriver,
)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
class DeployOrchestrator:
    def __init__(self, repo_dir: os.PathLike[str] | str, runner: Runner = real_runner):
        self.repo = Path(repo_dir).resolve()
        self.runner = runner
        self.state_dir = self.repo / ".vibecode"
        self.drivers: list[_DriverBase] = [d(runner=runner) for d in _REGISTRY]

    @property
    def driver_names(self) -> tuple[str, ...]:
        return tuple(d.name for d in self.drivers)

    def detect_target(self, prefer: str | None = None) -> DetectionResult:
        """Return a structured detection result without raising.

        - ``prefer`` set & known → ``DetectionResult(driver=match, ...)``.
        - ``prefer`` set & unknown → ``driver=None`` + helpful message.
        - ``prefer`` unset → walk drivers; first match wins; the full set
          of candidates is reported so a CLI/UI can render a picker.
        """
        if prefer is not None:
            for d in self.drivers:
                if d.name == prefer:
                    return DetectionResult(
                        driver=d,
                        candidates=(d.name,),
                        message_vi=f"Đã chọn target {d.name!r}.",
                        message_en=f"Selected target {d.name!r}.",
                    )
            return DetectionResult(
                driver=None,
                candidates=(),
                message_vi=(
                    f"Target {prefer!r} không tồn tại. " f"Hỗ trợ: {', '.join(self.driver_names)}."
                ),
                message_en=(
                    f"Unknown target {prefer!r}. " f"Available: {', '.join(self.driver_names)}."
                ),
            )

        candidates = tuple(d.name for d in self.drivers if d.detect(self.repo))
        if candidates:
            chosen = next(d for d in self.drivers if d.name == candidates[0])
            return DetectionResult(
                driver=chosen,
                candidates=candidates,
                message_vi=f"Auto-detect: {chosen.name!r}.",
                message_en=f"Auto-detected: {chosen.name!r}.",
            )
        return DetectionResult(
            driver=None,
            candidates=(),
            message_vi=(
                "Không auto-detect được deploy target. "
                "Truyền `--target=<name>` với một trong: "
                f"{', '.join(self.driver_names)}."
            ),
            message_en=(
                "Could not auto-detect a deploy target. "
                "Pass `--target=<name>` with one of: "
                f"{', '.join(self.driver_names)}."
            ),
        )

    def select_target(self, prefer: str | None = None) -> _DriverBase:
        """BC wrapper around ``detect_target()`` — raises on no match."""
        result = self.detect_target(prefer=prefer)
        if result.driver is not None:
            return result.driver
        if prefer is not None:
            raise ValueError(result.message_en)
        raise RuntimeError(result.message_en)

    def run(self, target: _DriverBase | str, opts: dict[str, Any] | None = None) -> DeployResult:
        if isinstance(target, str):
            target = self.select_target(prefer=target)
        opts = dict(opts or {})

        issues = target.preflight(self.repo)
        if any(i.severity == "error" for i in issues):
            errs = ", ".join(i.message for i in issues if i.severity == "error")
            return DeployResult(
                target=target.name,
                success=False,
                url=None,
                snapshot_id="",
                duration_s=0.0,
                log_excerpt=f"preflight failed: {errs}",
            )

        result = target.deploy(self.repo, opts)
        self._record(target.name, result)
        return result

    def rollback(self, snapshot_id: str) -> bool:
        for d in self.drivers:
            if d.rollback(snapshot_id):
                return True
        return False

    def history(self) -> list[dict[str, Any]]:
        log = self.state_dir / "deploy-history.jsonl"
        if not log.is_file():
            return []
        out: list[dict[str, Any]] = []
        for line in log.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out

    # -- internals -------------------------------------------------------
    def _record(self, target: str, result: DeployResult) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        (self.state_dir / "deploy-target.txt").write_text(target + "\n", encoding="utf-8")
        if result.url:
            (self.state_dir / "deploy-url.txt").write_text(result.url + "\n", encoding="utf-8")
        log = self.state_dir / "deploy-history.jsonl"
        with log.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "target": target,
                        "success": result.success,
                        "url": result.url,
                        "snapshot_id": result.snapshot_id,
                        "duration_s": result.duration_s,
                        "ts": int(time.time()),
                    }
                )
                + "\n"
            )


__all__ = [
    "DeployOrchestrator",
    "DeployResult",
    "Issue",
    "RunResult",
    "DryRunner",
    "real_runner",
    "VercelDriver",
    "DockerDriver",
    "VPSDriver",
    "CloudflareDriver",
    "RailwayDriver",
    "FlyDriver",
    "RenderDriver",
]
