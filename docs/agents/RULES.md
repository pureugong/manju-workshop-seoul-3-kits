# Rules (mmk-crew) — mostly don'ts

Guidance, not a harness. ⛔ marks the rules git itself enforces (`.claude/hooks/guard.py` on every commit and push,
no model involved — the commit fails with the reason); the rest you keep yourself. Escape hatches on the line:
`quarantine #N`, `-- contract: #N`, `guard: allow <check>` (with a reason in the PR). When a rule and the task collide,
keep the rule, do the task another way, and write `decided: …` in the PR. Project-specific rules go at the end.

## Working alone

- Don't ask the owner what you can decide. Ask only product direction; everything else: decide, note it, carry on.
- Don't widen scope. Something outside the story you noticed → a follow-up issue (or a line in the PR), not this PR.
- Don't split a story. API, screen, infra and docs for one story land in one PR. Docs, config syncs and kit updates ride
  along with the next feature PR instead of their own PR.
- Don't refactor, rename or reformat code the issue doesn't need.
- Don't add a dependency without one line in the PR saying why and what it costs (size, license).
- Don't silence an error to make something pass (empty catch, `|| true`, `skip`): fix it or say why in the PR.
- ⛔ Don't leave a TODO without an issue number (`TODO(#123)`).
- ⛔ Don't commit secrets or `.env` files; don't commit real user data or screenshots of real data.
- Don't change behaviour people see without updating the guide or docs that describe it.

## Tests

Where each kind of test goes:

| Kind | For | Size |
|---|---|---|
| Unit | pure logic: calculations, parsing, state machines, planners | many, milliseconds each |
| Integration | a boundary: the database, an HTTP API, a queue — against the real thing (container/local), not a mock | few per boundary |
| e2e | a flow a user depends on, end to end in the real app | few, named per area in WORKFLOW.md |
| Probe | long-run behaviour (performance, simulations, stability) measured over minutes | when the issue is about numbers |

Don'ts:
- Don't fix a bug without first writing the test that fails because of it.
- Don't cover with e2e what a unit test can cover. If logic is hard to unit-test, pull it out into a pure function.
- Don't mock your own code; mock only what you don't own and can't run (third-party APIs, payment, email).
- Don't sleep in tests. Wait for a condition; drive time with a fake clock; seed randomness.
- Don't share state between tests (order must not matter); don't depend on the network or the wall clock.
- ⛔ Don't weaken, skip or delete a failing test to get green. A flaky test → an issue (`[Bug] flaky …`) and a quarantine
  note in the test, never a silent retry loop.
- ⛔ Don't commit `.only` / focused tests.
- Don't let a new e2e take minutes when a cheaper check proves the same thing; e2e time is the coordinator's time.
- Don't call it done without running: typecheck, lint, unit tests, and the e2e for the areas you touched (or naming
  them in the PR when your machine can't run them).

## Data and compatibility (databases, APIs, events, config, files)

During a deploy the old code and the new code run against the same database, clients and stored files. Every change
must work with both.

- ⛔ Don't drop or rename a column/table/field in the same change that stops using it. **Expand → migrate → contract**,
  each its own deploy: add the new (nullable or with a default) → write both / backfill → switch reads → remove the old.
- ⛔ Don't add a `NOT NULL` column without a default; don't change a column's type in place (add a new one, backfill).
- ⛔ Don't edit a migration that has run anywhere (in `origin/main`); add a new one. Migrations forward-only unless the project says
  otherwise, safe to re-run, and not locking big tables for long (batch backfills).
- Don't deploy code that needs a migration before the migration has run.
- Don't delete user data in a migration without a backup or a soft delete.
- APIs, events, webhooks: additive only — new optional fields, new endpoints. Don't remove or rename a field, change
  its type or meaning, or make an optional field required; version the API when you truly must break it.
- Readers are tolerant: ignore unknown fields, default missing ones. Never reuse a field name for a new meaning.
- Config and env: a new setting has a safe default; an old one keeps working (deprecate first, remove later).
- Saved files and local storage (localStorage, caches, exports): read the old format, write the new.
- Say in the PR which deploy step this is (expand / migrate / contract) and what the next step is (a follow-up issue).

## Temporary cloud resources (test servers, instances, test stacks)

A test server once ran for five months with RDP open to the world and spent about $540 of credits (2026-11-08,
mmk-window-server issue 1). A scheduled check is only a safety net; the session that started it takes it down.

- ⛔ Don't start one without an expiry (TTL, default 24 h) and an automatic teardown created with it. Never a value
  that turns the shutdown off (`0`, `never`).
- When the work ends, take it down then and there, and confirm in the cloud that it is gone (no stack, instance
  terminated); say so in the PR or issue.
- Open admin ports (RDP, SSH) to your own IP only.
- A periodic sweep: pick its interval from the Actions minutes it costs (a rare one such as weekly, or a
  one-off schedule on the cloud side).

## Rules and the checks that keep them

A rule that slipped twice gets a check, in this order: structure (make it impossible), a hook or script, a test; a
doc line last. A new check must fail on a real past case before it lands. The coordinator reads this table when a
rule slips: a row without a check gets an issue.

| Rule | Checked by | When |
|---|---|---|
| Edit only under a claim, only its `Touches` | `coord.py` pre-edit hook (cloud sessions) | every edit |
| Cloud sessions never push `main`, merge, delete branches, deploy | `coord.py` pre-bash hook | every shell command |
| Commit, push, PR and ready before stopping | `coord.py` stop hook (cloud sessions) | session end |
| No TODO without an issue; no secrets, `.env`, oversized files | `guard.py` (todo, secret, env, size) | commit, push |
| No focused tests; no new skip in the diff | `guard.py` (focused, skip; `quarantine #N` lets a skip through) | commit, push |
| No more skipped tests than `main` at run time | `scripts/skips.py compare` in `mmk-crew-verify` | verify |
| Migrations: expand → migrate → contract; never edit one that ran; no `NOT NULL` without a default | `guard.py` (migration) | commit, push |
| PR body: issue link, evidence sections, spec rows | `.claude/bin/ready` (`coord.json` `prBody.mode`) | ready |
| A bug: the failing test committed first; before and after output | `.claude/bin/ready` (bug check) | ready |
| PR base is the default branch, or an agreed epic | `ready` note; `mmk-crew-verify` step 1 | ready, verify |
| An issue closes when its PR merges, also outside the default branch | `.claude/bin/close-merged` (post-merge, daily) | daily |
| One `status:*` on open issues, none on closed ones | `.claude/bin/labels` (post-merge, daily) | daily |
| The app starts, and every e2e passes, also those outside `Checks:` | `docs/agents/VERIFY.md` full run (coordinator) | daily |
| Releases keep pace with merges | `scripts/cadence.py` line in the report | each report |
| API and event fields additive; tolerant readers; screenshots from mock data | `mmk-crew-verify` diff review (judgement) | verify |
| Temporary cloud resources: TTL and auto teardown from the start, taken down and confirmed gone, admin ports to one IP | review list (`mmk-crew-verify` 3, `mmk-crew-release` 2) | verify, release |

## Project-specific

_(add the project's own rules here: performance budgets, design system, domains that need care…)_

## This project

- ⛔ Don't edit `README.md`, `setup-check/`, `cleanup/` or `.github/build.py` here. They come from the private course
  repo (`scripts/publish-kits.py`); a change made here is overwritten by the next publish. Change the source and publish.
- ⛔ This repository is public, branches included. Don't push workshop site addresses, internal names, account
  numbers, emails, tokens or placeholders (`[확인 필요`, TODO without an issue). Run the Checks before every push.
- ⛔ Don't delete, move or reuse a `seoul-3-vN` tag or Release: the kits compare the student's `VERSION` with the
  latest tag, and pinned addresses (`releases/download/seoul-3-vN/…`) must keep working after the workshop.
- ⛔ Cloud sessions don't publish, release, run workflows or change visibility (`deployPattern` in `.claude/coord.json`).
- New zips besides the kits (for example a starter pack) go in `extras/` only after the owner approves the terms of use;
  the scan reads every text file inside the zip and stops on binaries, links, paths outside the folder and secrets.
