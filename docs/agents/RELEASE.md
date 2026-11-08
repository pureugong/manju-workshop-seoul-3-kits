# Releases and tags (managed by mmk-crew; refreshed on every setup)

Human version (Korean): mmk-crew docs/400-reference/407-release-and-tags.md.

- **When**: a release = a milestone that is done and deployed (or ready to ship), not every merge. Cloud sessions
  never tag, release or deploy; the coordinator does, from `main`, after local checks pass.
- **Versions**: SemVer `vX.Y.Z`, start at `v0.1.0`. In 0.x: `feat` → minor, `fix`/`perf` → patch; a breaking change
  (`feat!:` or `BREAKING CHANGE:`) bumps minor until 1.0. `v1.0.0` = the owner says it is stable for others.
- **Tags**: `vX.Y.Z`, annotated, on a `main` commit. Monorepo: `<component>-vX.Y.Z`. Never move or delete a pushed tag:
  fix forward with a new patch.
- **Commits / PR titles**: Conventional Commits (`feat(scope): …`, `fix: …`, `docs:`, `chore:`, `refactor:`, `test:`,
  `ci:`, `perf:`). The squash-merge title is what goes into the notes, so write it for a reader.
- **How the tag is made** (the repo picks one; see `## Release` in its CLAUDE.md or README):
  1. release-please (`setup --release`): merge the open `chore(main): release x.y.z` PR → tag + GitHub Release.
  2. local script (`./release.sh X.Y.Z`): checks, bump version files, CHANGELOG, tag, push tag, `gh release create`.
  3. by hand: `git tag -a vX.Y.Z -m "vX.Y.Z" && git push origin vX.Y.Z && gh release create vX.Y.Z --generate-notes`.
- **GitHub Release body**: `## 요약` (1 to 3 Korean lines: what a user gets) / `## 바뀐 것` (새 기능, 고친 것) /
  `## 배포` (image tag, URL or download, migration steps) / `## 되돌리기` (previous tag). Assets: binaries or app
  zips with a `SHA256SUMS` when there is something to download.
- **Deploy ↔ tag**: deploy from a tag, and record the tag where the deploy lives (Docker image `:vX.Y.Z` plus `:latest`,
  Vercel deployment meta or alias note, Lambda alias/description, `version` endpoint or footer). Rollback = redeploy the
  previous tag, never a hand edit in production.
- **Actions** (the owner pays): no `push:` trigger. release-please runs on merged PRs or by hand, one ubuntu job.
  macOS/Windows builds only on a `v*` tag or `workflow_dispatch`, and only when the owner asked.
- **No releases** for docs/config/ops repos and one-off sites: they deploy from `main`; skip tags unless asked.

- **Production rollout** (production DB, functions, permissions or customer images; or the owner asks for a release):
  skill `mmk-crew-release`, runbook skeleton `docs/agents/RELEASE-RUNBOOK.md`, repo settings in `.claude/coord.json` `release`.
- Web deploys (Vercel projects): Vercel builds only the `release` branch. The coordinator deploys by fast-forwarding it, `git push origin origin/main:release`, when a release is wanted; merging to main does not deploy.
- Before a production release (negative check): never release without logs. Every new path logs start, result and failures with `error_kind` and `error` (docs/agents/LOGGING.md). If the failure log sample is missing, the release waits.
