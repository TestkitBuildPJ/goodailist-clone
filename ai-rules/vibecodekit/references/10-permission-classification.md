# Pattern #10 — Permission classification pipeline

**Source:** `utils/permissions/` 9 409 LOC (Giải phẫu §5)

## The 6 layers

| Layer | Name                   | Action                                                |
|-------|------------------------|-------------------------------------------------------|
|   1   | Safe allowlist         | Always allow (FileRead, Grep, Glob, TaskList-like)    |
|   2   | Permission mode        | `plan` / `default` / `accept_edits` / `bypass` / `auto` / `bubble` |
|   3   | User rules             | Match `exact` / `prefix` / `wildcard` rules           |
|   4   | Dangerous patterns     | Block regex-matched destructive ops                   |
|   5   | Command security       | Block shell-injection, Zsh tricks, heredoc-subst      |
|   6   | Denial tracking        | Fall back to user after N consecutive / M total       |

## v0.7 dangerous-pattern coverage (40+)

- **Destructive filesystem**: `rm -rf /`, `find -delete`, `mkfs.*`, `dd of=/`,
  `shred`, fork bombs.
- **RCE**: pipe to interpreter, `eval`, curl/wget piped to shell, base64
  decode piped to `bash`, interactive SSH spawn.
- **Privilege**: `sudo`, `setcap`, `chmod u+s`.
- **Git**: force push, `reset --hard`, `clean -fdx`, `filter-branch`,
  interactive rebase, `worktree remove --force`.
- **k8s/Terraform/Cloud**: `kubectl delete|apply|rollout|scale|patch|drain`,
  `helm install|delete|rollback`, `terraform apply|destroy|taint`,
  `aws|gcloud|az ... delete`, `aws s3 rb`.
- **Containers**: `docker rm|kill|prune|volume rm`, `docker-compose down -v`.
- **DB**: `DROP TABLE|DATABASE`, `TRUNCATE`, `DELETE` without `WHERE`,
  `prisma|alembic|knex migrate deploy|reset`.
- **Package install**: `npm|yarn|pnpm install`, `pip install`, `cargo install`,
  `apt install`, `brew install`.
- **Secrets**: `.env`, `.env.local|production|...`, `~/.aws/credentials`,
  `~/.ssh/id_*`, specific env-var names.
- **Shell injection**: Zsh `=cmd` expansion, `=(...)` array construction,
  heredoc with `$(...)`, dangerous Zsh builtins.
- **Deploy**: `vercel|netlify|fly|heroku|railway|serverless deploy`.

## False-positive fixes vs v0.6
- `.env.example` / `.env.sample` / `.env.dist` / `.env.template` are allowed.
- `env FOO=1 pytest` is allowed (the `env` token is a command, not a file).

## Circuit breaker tuning
- `max_consecutive = 3`, `max_total = 20`, `ttl_seconds = 24 * 3600`.
- Repeated denial of the **same** command: `≥ 2` prior hits within TTL
  triggers the short-circuit deny (v0.6 was `= 1`, which blocked
  legitimate re-attempts).

## How v0.7 enforces it
- `permission_engine.decide()` implements all 6 layers.
- 70+ probe commands in `tests/test_permission_engine.py`.
- Probe `10_permission_classification` covers the happy + dangerous mix.
