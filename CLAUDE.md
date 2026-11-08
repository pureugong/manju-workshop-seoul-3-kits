# manju-workshop-seoul-3-kits — notes for every Claude session

Public release repository for the 만쥬 워크샵 IN SEOUL 3회 (2026-11-15) student kits. Students paste one line into the
Claude app; Claude downloads `setup-check.zip` or `cleanup.zip` from this repo's Releases and follows the `.md` inside.

## Who owns what

| Path | Owner | How it changes |
|---|---|---|
| `README.md`, `setup-check/`, `cleanup/`, `.github/build.py` | the private course repo's `scripts/publish-kits.py` | a `publish/<rev>` PR opened by that script; never edit them here |
| everything else (`CLAUDE.md`, `docs/`, `.claude/`, `.github/` other files) | this repo | a normal PR here |

- This repo is **public**. Everything pushed, branches included, is visible at once. Never write workshop site
  addresses, internal names, account numbers, emails or secrets here; `python3 .github/build.py check` scans the
  published files, and the course repo adds private host rules on top before each publish.
- Releases are versioned `seoul-3-vN`. Each zip holds `<kit>/VERSION`. The kits read the latest tag from
  `api.github.com/repos/pureugong/manju-workshop-seoul-3-kits/releases/latest` to tell students when their copy is old,
  so never delete or rename a published tag. Flow: docs/100-overview/101-release-flow.md, runbook docs/500-runbooks/501-release.md.

<!-- mmk-crew:begin (managed by github.com/pureugong/mmk-crew; edit the project parts outside this block) -->
## Coordination (mmk-crew — enforced by hooks; read docs/agents/CLOUD.md)

One **coordinator** (the owner's local session) and up to `maxCloud` **cloud** sessions work here at once.

- Related issues are bundled: one bundle = one session, one branch, one PR (a commit per issue). Cloud only for a small issue that touches nothing else in flight.
- One GitHub issue per claim. Titles `[Bug]/[Story]/[Task]` + `type:*` label. Claim before editing:
  `.claude/bin/claim <issue> --branch cloud/<slug> --touches <path[#symbol]> ... --title "<what>"`.
  Refused → comment "blocked" on the issue and stop. `.claude/bin/claims` lists open claims.
- Edit only what your claim `Touches` (widen it with the same command). Push only your work branch, every ≤30 min.
- Cloud sessions never push `main`, merge, delete branches or deploy. `gh issue`/`gh pr` get 403 in the cloud: use
  `gh api` REST. Never ask the owner: decide, write `decided: …` in the PR, carry on.
- Finish: one PR per issue (`.github/pull_request_template.md`: evidence, mock-data screenshots as pinned `<img>`,
  the e2e the coordinator must run), mark it ready, `.claude/bin/ready <issue> <pr>`, then stop — no subscription,
  check-in, wakeup or trigger.
- The coordinator verifies in a scratch worktree, merges at ~90% (follow-up issues for the rest), deploys, closes,
  `.claude/bin/release <issue>`. Flow: docs/agents/WORKFLOW.md. Running and proving the app: docs/agents/VERIFY.md.
- Commit messages end with the `Claude-Session:` trailer of the session that wrote them. No GitHub Actions unless
  the owner asks (no `push:` triggers).
- Rules (mostly don'ts: testing, data/API compatibility, working alone): docs/agents/RULES.md — read before coding.
- Korean a person reads (docs, UI, PR, reports): docs/agents/KOREAN.md — no calques (provider → 프로바이더), no 「수 있」, dashes, middots. Terms: docs/agents/GLOSSARY.md (add new ones in the same PR).
- One product, one repo (monorepo: folders, not new repos). Owner defaults (Go router, middleware, AWS/Terraform/tags, subdomain, Google login, UI kit, buttons, brand logos, dark+light, 4 screenshots, measured alignment): docs/agents/STACK.md.
- Temporary cloud resources (test servers, instances, stacks): TTL (default 24 h) and auto teardown from the start, RDP/SSH to your IP only, take it down when done and confirm it is gone (RULES.md).
- Logging (JSON lines, fixed fields, request id, failure reason; never release to production without logs): docs/agents/LOGGING.md.
- Releases and tags (when, SemVer vX.Y.Z, Conventional Commits, release body, deploy from a tag, rollback = previous tag): docs/agents/RELEASE.md. A production release: skill `mmk-crew-release`.
- Checks: `python3 .github/build.py check && bash -n setup-check/check.sh` (no pwsh here: check.ps1 is checked on the Windows test machine)
<!-- mmk-crew:end -->
