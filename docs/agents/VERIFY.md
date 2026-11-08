<!-- Project-owned: setup writes this file once and never again. Fill it during onboarding and keep it true. -->
# Verify the app

How any session, local or cloud, proves this app works: start it, see it is up, drive it, keep evidence, clean up.
Areas and their e2e are in [WORKFLOW.md](WORKFLOW.md); this file is how to run them.

- Onboarding runs all five steps once and writes the first line of "Last full run".
- The coordinator runs all five steps once a day (every e2e here, also those outside the `Checks:` line).
- A step that stopped working → an issue (`[Task] VERIFY.md: <step> broken`, or `[Bug]` when the app is wrong).
  Never edit this file to hide a product regression.

## 1. Start

Nothing runs as a server. "Starting" is building the zips the way a Release does, into a temp folder:

```sh
T=$(mktemp -d)
python3 .github/build.py zip "$T/dist" seoul-3-v0     # scans first; stops on any match
```

## 2. Health

`build.py zip` printed `검사: 이상 없음` and one line per kit (`setup-check.zip: …`, `cleanup.zip: …`), and:

```sh
for k in setup-check cleanup; do unzip -Z1 "$T/dist/$k.zip"; unzip -p "$T/dist/$k.zip" "$k/VERSION"; done   # → seoul-3-v0
```

## 3. Drive

```sh
(cd "$T" && unzip -oq dist/setup-check.zip && bash setup-check/check.sh --plan)   # read-only install plan, changes nothing
```
After a real Release, as a student would get it (no login):
```sh
for k in setup-check cleanup; do
  curl -sL -o "$T/$k.zip" -w "$k %{http_code}\n" https://github.com/pureugong/manju-workshop-seoul-3-kits/releases/latest/download/$k.zip
  unzip -p "$T/$k.zip" "$k/VERSION"
done
curl -fsSL https://api.github.com/repos/pureugong/manju-workshop-seoul-3-kits/releases/latest | grep '"tag_name"'
```
Windows (`check.ps1`, `Expand-Archive`, `Invoke-RestMethod`): on the Windows test machine, by pasting the README line
into the Claude app. Not possible in a cloud session.

## 4. Evidence

The `build.py` output (file list, scan result), the `unzip -Z1` lists, the VERSION lines, the HTTP codes. Paste them
into the PR. No screenshots unless the README's look changed.

## 5. Clean up

`rm -rf "$T"`.

## What counts as evidence

| Feature or area | Evidence | Command |
|---|---|---|
| Setup check kit | zip list, VERSION, `--plan` output | steps 1 to 3 |
| Cleanup kit | zip list, VERSION | steps 1 to 2 |
| Release | both `latest` addresses 200 without login, VERSION = the new tag, API `tag_name` = the new tag | step 3 |

## Last full run

| Date | Who | Result | Issues opened |
|---|---|---|---|
| 2026-11-08 | onboarding session (master befcc3f) | steps 1 to 5 pass: scan ok (7 files, 10 rules), both zips with VERSION, `check.sh --plan` ends 「판정: 오늘 실습 준비 완료」 on the Mac, both `latest` addresses 200 without login with VERSION seoul-3-v1. check.ps1 not run here (no pwsh) | none |
