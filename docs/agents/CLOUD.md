# Multi-session protocol: one coordinator, many cloud sessions (mmk-crew)

Enforced by hooks: `.claude/settings.json` → `.claude/hooks/coord.py`. Scripts: `.claude/bin/{claim,claims,ready,release,prune}`.
Config: `.claude/coord.json` (`maxCloud`, `hot` files, `free` paths, `deployPattern`, `mode: enforce|log`).
Local state (gitignored): `.claude/state/`. Flow and diagrams: [WORKFLOW.md](WORKFLOW.md). Running the app and what
counts as evidence: [VERIFY.md](VERIFY.md).

## Roles

| Role | Who | How the hook tells |
|---|---|---|
| coordinator | The one local session the owner talks to. Creates issues, launches sessions, verifies, merges, deploys, releases. | not remote, and `session_id` == `.claude/state/coordinator` |
| cloud | Any `claude --cloud` session, any number up to `maxCloud`. | `CLAUDE_CODE_REMOTE=true` |
| local | Any other local session. Told the protocol, never blocked. | otherwise |

Identity = `CLAUDE_CODE_REMOTE_SESSION_ID` (cloud) or the hook's `session_id`. Commits end with
`Claude-Session: https://claude.ai/code/session_…`; claims, PRs and comments carry the same link.

## Unit of work: one issue, claimed atomically

1. Every task is a GitHub issue. Title prefix `[Bug]` / `[Story]` / `[Task]` + label `type:bug|story|task`.
   Bug = broken. Story = something people see or use. Task = docs, tooling, tests, process.
   Only the coordinator creates issues. Dependencies go in the body as `Starts after #N`.
2. A claim is a ref `refs/claims/issue-<N>` with one commit, pushed with an empty lease → of two racing sessions
   exactly one wins (branch `claim/issue-<N>` only where the cloud proxy refuses the ref). Only the coordinator deletes it (`release`).
3. The claim commit records `Claim-Session`, `Work-Branch`, `Base`, and one `Touches: <file>[#symbol]` per edit target.
4. `claim` refuses: the same `file#symbol` held by another claim; a whole-file claim on a `hot` file; the issue
   already held. It warns on the same file at different symbols. Refused → comment "blocked by #M" and stop.
5. Labels: `status:todo` → claim → `status:in-progress` → `ready` → `status:review` → merge + `release` → closed.
   The post-merge hook (`coord.py labels`, daily) fixes what slips: none on closed issues, one on open ones.
   One `status:*` at a time; the scripts swap them. Leftover work = a new issue; closed issues are not reopened.
   The claim comment is one comment per issue, edited in place (`<!-- coord:claim -->`).

## Working (cloud)

- Claim first: `.claude/bin/claim <N> --branch cloud/<slug> --touches <file[#symbol]> … --title "<what>"`.
  Edits outside `Touches` are denied: widen the claim with the same command (repeat `--touches` or list several after one; both add). Local worktree sessions set `MMK_CREW_SESSION=<their session id>` so their claims stay theirs.
- Push the work branch at least every 30 min; merge `origin/main` in often; `--force-with-lease` only.
- `gh issue` / `gh pr` get 403 in the cloud (GraphQL): use `gh api` REST.
- Never ask the owner. Pick the safest sensible option, note it in the PR as `decided: …`, carry on.
  `blocked:` only for what truly cannot be done (a missing secret, a refused claim).
- Secrets the cloud lacks (TTS keys, paid APIs): list what needs doing locally on the issue; the coordinator does it.

## Finishing

- One PR per issue, body per `.github/pull_request_template.md`: `Closes #N`, what/why, evidence (before → after
  numbers with commands, screenshots from mock data as `<img>` pinned to a commit sha, command output), and the
  e2e the coordinator must run locally (the cloud's browser is slow software GL).
- A bug: commit the test that reproduces it first, alone (it fails), then the fix; paste both runs under
  "Before and after".
- `ready` checks the body: a `Closes`/`Refs` link and every evidence section filled (for a bug, "Before and after"
  and the test commit before the fix). In `enforce` it refuses until
  fixed; in `log` it notes what is missing in the ready comment. Fix what it lists rather than leave the note.
- Mark it ready (`gh api -X PATCH …/pulls/<pr> -F draft=false`), then `.claude/bin/ready <N> <pr>` and **stop**:
  no PR subscription, check-in, wakeup or trigger. The coordinator watches for "ready".
- Cloud sessions never push `main`, merge a PR, delete a branch, or deploy. The hooks deny it.

## Coordinator

- Verify in a scratch worktree, never on `main`: `git worktree add <scratch>/verify origin/main`, link dependencies,
  merge ready PRs `--no-ff`, run checks there; only when green fast-forward `main`, push, deploy once.
- Several PRs ready: merge them together, run typecheck/lint/unit once plus the union of the e2e each names.
- Merge bar ~90%: send back only critical failures; fix minor ones inside the story in the same PR (follow-up issues only for work beyond the story); fix tiny ones
  in the verify worktree. See WORKFLOW.md.
- Release in the same command chain as the push to main (`&& .claude/bin/release <N>`), then comment in the verify
  skill's fixed form (what ran with counts, skipped vs main, what did not run), close, delete the work branch only
  after `git merge-base --is-ancestor origin/<branch> origin/main`. PR base not the default branch: check it first
  (an agreed epic, or retarget); after merging into an epic `.claude/bin/close-merged` closes the issue.
- Stale branches: git `post-merge` hook → `coord.py prune --local` each merge, `--remote` daily. Unmerged branches
  idle 7+ days are kept as `refs/pruned/*` and deleted; every deletion is logged with its sha. Never removed: a branch
  with no commit of its own (only created, fast-forwarded or reset), a worktree a process works in, a dirty one.

## Hooks

| Hook | Applies to | Does |
|---|---|---|
| SessionStart | all | writes identity; injects role, protocol summary, open claims |
| PreToolUse Edit/Write | cloud | deny without a claim; deny paths outside `Touches` (except `free`) |
| PreToolUse Bash | cloud | deny push to `main`/other branches, force without lease, branch delete, PR merge, deploy (`deployPattern`), `release` |
| Stop | cloud | block (max 3) while: uncommitted, unpushed, no PR, no ready/blocked comment |

Hooks fail open (errors → `.claude/state/coord.log`). `mode: "log"` turns denies into log lines.
