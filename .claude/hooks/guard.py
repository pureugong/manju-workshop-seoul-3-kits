#!/usr/bin/env python3
"""
mmk-crew guard: the rules in docs/agents/RULES.md that a machine can check, checked by a machine — no model, no tokens.

  guard.py staged            the staged diff (git pre-commit; Claude's PreToolUse on `git commit`)
  guard.py all               everything tracked against HEAD (`git commit -a`)
  guard.py range <base>      the commits since <base> (Claude's PreToolUse on `git push`: base = origin/main)

Exit 1 with one line per finding when something must not go in. Config: `guards` in .claude/coord.json:
  "guards": {"migrations": ["**/migrations/**"], "maxFileMB": 5, "off": ["todo"], "skip": ["vendor/**"]}
Escape hatches, on the line itself: `quarantine #N` (a skipped test with its issue), `-- contract: #N` (a destructive
migration as the contract step of an expand/contract change), `guard: allow <check>` (anything else, with a reason).
"""
import fnmatch
import json
import os
import re
import subprocess
import sys


def git(*a):
    return subprocess.run(['git', *a], capture_output=True, text=True).stdout


root = git('rev-parse', '--show-toplevel').strip() or '.'
os.chdir(root)
try:
    CFG = json.load(open('.claude/coord.json')).get('guards', {})
except Exception:
    CFG = {}
OFF = set(CFG.get('off', []))
MIG = CFG.get('migrations', ['**/migrations/**', '**/migrate/**', 'db/schema/**', '**/*.migration.sql'])
MAX_MB = float(CFG.get('maxFileMB', 5))
# paths the line checks skip: mmk-crew's own files (they spell out the patterns they look for), plus the project's
SKIP = ['.claude/hooks/**', '.claude/bin/**'] + CFG.get('skip', [])

mode = sys.argv[1] if len(sys.argv) > 1 else 'staged'
if mode == 'range':
    base = sys.argv[2] if len(sys.argv) > 2 else 'origin/main'
    rng = [f'{base}...HEAD']
    names = git('diff', '--name-status', *rng)
    diff = git('diff', '-U0', *rng)
elif mode == 'all':  # `git commit -a`: what is about to be committed is everything tracked
    rng = ['HEAD']
    names = git('diff', 'HEAD', '--name-status')
    diff = git('diff', 'HEAD', '-U0')
else:
    rng = ['--cached']
    names = git('diff', '--cached', '--name-status')
    diff = git('diff', '--cached', '-U0')

TEST = re.compile(r'(\.(test|spec)\.[cm]?[jt]sx?$|_test\.go$|/tests?/|\.rs$)')
CHECKS = {
    'focused': (TEST, re.compile(r'\b(it|test|describe)\.only\s*\(|\bf(it|describe)\s*\(|\.only\(')),
    'skip': (TEST, re.compile(r'\b(it|test|describe)\.skip\s*\(|\bx(it|describe)\s*\(|\bt\.Skip\(|#\[ignore\]|test\.fixme\(')),
    'secret': (None, re.compile(r'(AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|\bsk-[A-Za-z0-9_-]{20,}|\bghp_[A-Za-z0-9]{30,}|'
                                r'\bgithub_pat_[A-Za-z0-9_]{30,}|\bAIza[0-9A-Za-z_-]{30,}|\bxox[baprs]-[A-Za-z0-9-]{10,}|'
                                r'(?i:(api[_-]?key|secret|password|token)\s*[:=]\s*["\'][^"\'\s]{12,}["\']))')),
    'todo': (None, re.compile(r'\b(TODO|FIXME|XXX)\b(?!.*#\d+)')),
}
DESTRUCTIVE = re.compile(r'(?i)\b(drop\s+(table|column|index|constraint)|rename\s+(to|column)|alter\s+column\s+\S+\s+(set\s+data\s+)?type|'
                         r'alter\s+table\s+\S+\s+alter\s+.*\bnot\s+null|truncate\b|delete\s+from\b)')
NOTNULL_NODEFAULT = re.compile(r'(?i)\badd\s+(column\s+)?\S+\s+[^,;]*\bnot\s+null\b(?![^,;]*\bdefault\b)')

found = []


def allowed(line, check):
    return f'guard: allow {check}' in line


def is_mig(path):
    # (a leading **/ also matches at the top: migrations/001.sql)
    return any(fnmatch.fnmatch(path, g) or fnmatch.fnmatch('./' + path, g) for g in MIG)


# files: added/modified/renamed/deleted
status = {}
for ln in names.splitlines():
    p = ln.split('\t')
    if len(p) >= 2:
        status[p[-1]] = p[0][0]
        if p[0][0] == 'R':
            status[p[1]] = 'R'

for path, st in status.items():
    if 'env' not in OFF and re.search(r'(^|/)\.env(\.[\w.-]+)?$', path) and not path.endswith(('.example', '.sample', '.template')) and st != 'D':
        found.append(f'secret: {path} is an env file — keep it out of git (add a .example instead)')
    if 'migration' not in OFF and is_mig(path) and st in 'MRD':
        # an existing migration changed: was it already in main?
        base_ref = 'origin/main' if git('rev-parse', '--verify', '-q', 'origin/main').strip() else 'HEAD'
        if git('cat-file', '-t', f'{base_ref}:{path}').strip():
            found.append(f'migration: {path} already ran somewhere — add a new migration instead of editing/removing it')
    if 'size' not in OFF and st in 'AM' and os.path.isfile(path) and os.path.getsize(path) > MAX_MB * 1e6:
        found.append(f'size: {path} is {os.path.getsize(path) / 1e6:.1f} MB (limit {MAX_MB:g} MB in coord.json guards.maxFileMB)')

# added lines
cur = None
for ln in diff.splitlines():
    if ln.startswith('+++ '):
        cur = ln[6:] if ln.startswith('+++ b/') else None
        continue
    if not cur or not ln.startswith('+') or ln.startswith('+++') or any(fnmatch.fnmatch(cur, g) for g in SKIP):
        continue
    line = ln[1:]
    for name, (where, rx) in CHECKS.items():
        if name in OFF or (where and not where.search(cur)) or not rx.search(line) or allowed(line, name):
            continue
        if name == 'skip' and re.search(r'quarantine\s*#\d+', line):
            continue
        if name == 'todo' and re.search(r'\.(md|txt)$', cur):
            continue
        if name == 'secret' and re.search(r'(example|placeholder|dummy|xxxx|<[^>]+>|\$\{|process\.env|os\.environ|getenv)', line, re.I):
            continue
        msg = {'focused': 'a focused test (.only / fit) — the rest of the suite would not run',
               'skip': 'a test newly skipped — fix it, or mark the line `quarantine #<issue>`',
               'secret': 'something that looks like a secret — use an env var',
               'todo': 'a TODO without an issue number — write `TODO(#123)`'}[name]
        found.append(f'{name}: {cur}: {msg}\n    {line.strip()[:120]}')
    if 'migration' not in OFF and is_mig(cur) and not re.search(r'contract:\s*#\d+', line) and not allowed(line, 'migration'):
        if DESTRUCTIVE.search(line):
            found.append(f'migration: {cur}: destructive in one step — expand → migrate → contract; mark the contract '
                         f'step `-- contract: #<issue>`\n    {line.strip()[:120]}')
        elif NOTNULL_NODEFAULT.search(line):
            found.append(f'migration: {cur}: NOT NULL without a DEFAULT breaks the code still running\n    {line.strip()[:120]}')

if found:
    print('mmk-crew guard (docs/agents/RULES.md) — not committed:\n' + '\n'.join('- ' + f for f in found))
    sys.exit(1)
