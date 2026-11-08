#!/usr/bin/env python3
"""
Coordination for many Claude sessions on one repo (mmk-crew: github.com/pureugong/mmk-crew): one coordinator (local), any number of cloud sessions.
The protocol is docs/agents/CLOUD.md; this file is its enforcement.

  coord.py hook session-start|pre-bash|pre-edit|stop    (from .claude/settings.json; JSON on stdin)
  coord.py claim N --branch B --touches F[#symbol] ... [--title T] [--session S]
  coord.py release N                                    (coordinator only: after merge, or to reassign)
  coord.py ready N PR                                   (worker's last step: PR body check, status:review + "ready: PR #M")
  coord.py list
  coord.py labels [--dry-run]                           (status:* matches the issue state; daily)
  coord.py coordinator [session-id]                    (register the owner's local session as coordinator)
  coord.py prune --remote|--local [--dry-run]           (stale branches; run by the post-merge hook)
  coord.py close-merged [--days D] [--dry-run]          (issues closed by PRs merged outside the default branch; daily)

A claim is a ref `refs/claims/issue-<N>` (a branch `claim/issue-<N>` only where a cloud proxy refuses the ref) holding one
commit (main's tree, no change of its own) whose trailers say who holds the issue
(Claim-Session), where they work (Work-Branch) and what they will edit (Touches). Created with an empty
lease, so of two sessions racing for an issue exactly one wins.

Enforced for cloud sessions (CLAUDE_CODE_REMOTE=true). The coordinator is unrestricted; other local
sessions are told the protocol but not blocked. Any internal error lets the call through (fail open)
and is logged to .claude/state/coord.log.
"""
import fnmatch
import json
import os
import re
import shlex
import subprocess
import sys
import time

EMPTY_TREE = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'


def run(*a, cwd=None, inp=None):
    p = subprocess.run(list(a), cwd=cwd, capture_output=True, text=True, input=inp)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def top():
    _, out, _ = run('git', 'rev-parse', '--show-toplevel', cwd=os.environ.get('CLAUDE_PROJECT_DIR') or os.getcwd())
    return out or os.getcwd()


ROOT = top()
# (the main checkout's .claude/state, shared by its worktrees)
_, _common, _ = run('git', 'rev-parse', '--path-format=absolute', '--git-common-dir', cwd=ROOT)
MAIN = os.path.dirname(_common) if _common.endswith('/.git') else ROOT
STATE = os.path.join(MAIN, '.claude', 'state')
os.makedirs(STATE, exist_ok=True)
with open(os.path.join(ROOT, '.claude', 'coord.json')) as f:
    CFG = json.load(f)
REPO = CFG['repo']


def git(*a):
    return run('git', *a, cwd=ROOT)


def log(msg):
    with open(os.path.join(STATE, 'coord.log'), 'a') as f:
        f.write(time.strftime('%Y-%m-%dT%H:%M:%S ') + msg + '\n')


def norm(sid):
    """session ids come as cse_X (cloud env), session_X (commit trailers, claude.ai links) or a bare uuid"""
    sid = (sid or '').strip().rstrip('/').split('/')[-1]
    return re.sub(r'^(cse_|session_|local:)', '', sid)


def identity(hook_sid=''):
    remote = os.environ.get('CLAUDE_CODE_REMOTE') == 'true'
    sid = norm(os.environ.get('CLAUDE_CODE_REMOTE_SESSION_ID') or hook_sid)
    try:
        coord = norm(open(os.path.join(STATE, 'coordinator')).read())
    except OSError:
        coord = ''
    role = 'cloud' if remote else 'coordinator' if sid and sid == coord else 'local'
    return role, sid


def link(sid):
    return 'https://claude.ai/code/session_' + sid if sid and not re.match(r'^[0-9a-f-]{36}$', sid) else 'local:' + sid


# --- claims ---------------------------------------------------------------------------------------

def fetch_claims(max_age=60):
    stamp = os.path.join(STATE, 'claims.fetched')
    try:
        fresh = time.time() - os.path.getmtime(stamp) < max_age
    except OSError:
        fresh = False
    if not fresh:
        # claims live in refs/claims/issue-N (not branches: branch hooks such as Vercel deploy every push).
        # Old claim/issue-N branches are still read during the transition; new refs win.
        code, _, err = git('fetch', '-q', '--prune', 'origin', '+refs/heads/claim/*:refs/remotes/origin/claim/*',
                           '+refs/claims/*:refs/remotes/origin/claim/*')
        if code == 0:
            open(stamp, 'w').close()
        else:
            log('fetch claims failed: ' + err)
        return code == 0
    return True


def claims(max_age=60):
    fetch_claims(max_age)
    _, refs, _ = git('for-each-ref', '--format=%(refname:short) %(objectname)', 'refs/remotes/origin/claim/')
    out = []
    for line in refs.splitlines():
        ref, sha = line.split()
        m = re.search(r'claim/issue-(\d+)$', ref)
        if not m:
            continue
        _, body, _ = git('log', '-1', '--format=%B', sha)
        c = {'issue': int(m.group(1)), 'sha': sha, 'title': body.splitlines()[0] if body else '', 'touches': []}
        for k, v in re.findall(r'^([A-Za-z-]+):\s*(.+)$', body, re.M):
            if k == 'Touches':
                c['touches'].append(v.strip())
            elif k in ('Claim-Session', 'Claim-Role', 'Work-Branch', 'Base'):
                c[k] = v.strip()
        c['session'] = norm(c.get('Claim-Session', ''))
        out.append(c)
    return sorted(out, key=lambda c: c['issue'])


def describe(cs):
    if not cs:
        return '(none)'
    return '\n'.join(f"- #{c['issue']} {c.get('Claim-Role', '?')} {c.get('Claim-Session', '?')} on {c.get('Work-Branch', '?')}: "
                     + ', '.join(c['touches']) for c in cs)


def covers(touch, rel):
    f = touch.split('#')[0]
    return rel == f or (f.endswith('/') and rel.startswith(f)) or fnmatch.fnmatch(rel, f)


# --- hook output ----------------------------------------------------------------------------------

def deny(event, reason):
    if CFG.get('mode') == 'log':
        log(f'would deny ({event}): {reason}')
        return {}
    log(f'deny ({event}): {reason}')
    return {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
                                   'permissionDecisionReason': reason + '  (protocol: docs/agents/CLOUD.md)'}}


def install_git_hooks():
    """git's own hooks enforce the guard (guard.py) and branch pruning in every clone, cloud ones included.
    Links point into the MAIN checkout, never a worktree: worktrees share one hooks dir, and a link into a worktree
    breaks silently (git skips a missing hook) once that worktree is removed. A broken link, or a link into another
    checkout's .claude/hooks, is replaced; a regular file or another tool's working link is left alone. Returns the hooks that will not run."""
    _, hooks, _ = run('git', 'rev-parse', '--path-format=absolute', '--git-path', 'hooks', cwd=ROOT)
    if not hooks:
        return []
    os.makedirs(hooks, exist_ok=True)
    bad = []
    for name in ('pre-commit', 'pre-push', 'post-merge'):
        src = os.path.join(MAIN, '.claude', 'hooks', name)
        if not os.path.exists(src):  # main checkout older than this worktree: fall back to it, still better than none
            src = os.path.join(ROOT, '.claude', 'hooks', name)
        if not os.path.exists(src):
            continue
        dst = os.path.join(hooks, name)
        try:
            if os.path.islink(dst):
                cur = os.readlink(dst)
                ours = cur.endswith(os.path.join('.claude', 'hooks', name))
                if (cur == src or not ours) and os.path.exists(dst):
                    continue  # already right, or someone else's working link
                tmp = f'{dst}.mmk-crew.{os.getpid()}'
                os.symlink(src, tmp)
                os.replace(tmp, dst)
                log(f'git hook {name}: relinked {os.readlink(dst)}')
            elif not os.path.lexists(dst):
                os.symlink(src, dst)
        except OSError as e:
            log(f'git hook {name}: {e!r}')
        if not os.path.exists(dst):
            bad.append(name)
    return bad


def on_session_start(inp):
    bad_hooks = install_git_hooks()
    role, sid = identity(inp.get('session_id', ''))
    with open(os.path.join(STATE, f'identity-{sid or "unknown"}.json'), 'w') as f:
        json.dump({'role': role, 'session': sid, 'at': time.time()}, f)
    cs = claims(0)
    mine = [c for c in cs if c['session'] == sid]
    if role == 'cloud':
        ctx = f"""You are a CLOUD session ({link(sid)}) on {REPO}, one of possibly several running at once.
The coordination protocol (docs/agents/CLOUD.md) is enforced by hooks:
- Before editing any file you must hold a claim on your issue:
    .claude/bin/claim <issue> --branch cloud/<slug> --touches <path[#symbol]> ... --title "<what>"
  It fails if another session holds that issue or the same file#symbol (or a hot file: {', '.join(CFG['hot'])}).
  If it fails: comment on your issue "blocked by #M" (gh api REST) and stop. Do not work around it.
- Edits outside your Touches are denied; widen the claim first (run claim again with the extra --touches).
- Push only your Work-Branch. Never main, never a claim/* branch by hand, never --force (use --force-with-lease).
- Never merge a PR, never deploy. The coordinator verifies, merges and deploys.
- Finish with ONE PR for the issue (gh api repos/{REPO}/pulls -f head=<branch> -f base=main -f title=... -f body=...;
  gh pr / gh issue are GraphQL and get 403 here), body with Closes #N, numbers, demo-data screenshot paths and the
  e2e the coordinator must run locally; then run .claude/bin/ready <issue> <pr> (label + "ready: PR #M" comment).
- After `ready` you are done: stop. Do not subscribe to the PR, schedule a check-in or wakeup, or create a trigger or
  routine: the coordinator watches for "ready", and deleting a trigger later needs the owner to approve it by hand.
Your claims: {describe(mine)}
All open claims:
{describe(cs)}"""
    elif role == 'coordinator':
        ctx = f"""You are the COORDINATOR session for {REPO} (docs/agents/CLOUD.md): you assign issues, verify, merge,
deploy, and release claims after merging (.claude/bin/release <N>). Open claims:
{describe(cs)}"""
    else:
        ctx = f"""Several Claude sessions work on {REPO} (docs/agents/CLOUD.md). You are a local session, not the coordinator:
before editing, claim your issue (.claude/bin/claim <N> --branch <b> --touches ...) and keep off files other claims hold.
Open claims:
{describe(cs)}
This session's id: {sid}. If the owner makes this the coordinator: python3 .claude/hooks/coord.py coordinator {sid}"""
    if bad_hooks:
        ctx += (f"\nWARNING: git hooks {', '.join(bad_hooks)} do not resolve in this clone, so the guard and pruning are off. "
                "Tell the coordinator (see .claude/state/coord.log).")
    return {'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': ctx}}


def on_pre_edit(inp):
    role, sid = identity(inp.get('session_id', ''))
    if role != 'cloud':
        return {}
    ti = inp.get('tool_input') or {}
    path = ti.get('file_path') or ti.get('notebook_path') or ''
    if not path:
        return {}
    rel = os.path.relpath(os.path.realpath(path), os.path.realpath(ROOT))
    if rel.startswith('..') or any(rel.startswith(p) for p in CFG.get('free', [])):
        return {}
    mine = [c for c in claims() if c['session'] == sid]
    if not mine:
        return deny('pre-edit', f'This session ({link(sid)}) holds no claim. Claim your issue first: '
                                f'.claude/bin/claim <issue> --branch cloud/<slug> --touches {rel} ...')
    if not any(covers(t, rel) for c in mine for t in c['touches']):
        held = '; '.join(f"#{c['issue']}: " + ', '.join(c['touches']) for c in mine)
        return deny('pre-edit', f'{rel} is outside your claim ({held}). Widen it first: '
                                f".claude/bin/claim {mine[0]['issue']} --touches {rel}  (it re-checks other claims)")
    return {}


def push_targets(cmd):
    """the branches a shell command pushes to, and what is wrong with how (None if it does not push)"""
    targets, bad = [], []
    for seg in re.split(r'&&|\|\||;|\|', cmd):
        try:
            tok = shlex.split(seg)
        except ValueError:
            tok = seg.split()
        if 'git' not in tok or 'push' not in tok:
            continue
        rest = tok[tok.index('push') + 1:]
        flags = [t for t in rest if t.startswith('-')]
        pos = [t for t in rest if not t.startswith('-')]
        if any(f in ('--delete', '-d', '--mirror', '--all', '--tags', '--prune') for f in flags):
            bad.append('deleting or mass-pushing refs')
        lease = any(f.startswith('--force-with-lease') for f in flags)
        if not lease and any(f in ('--force', '-f') or f.startswith('--force=') for f in flags):
            bad.append('--force (use --force-with-lease)')
        specs = pos[1:]
        if not specs:
            _, cur, _ = git('rev-parse', '--abbrev-ref', 'HEAD')
            specs = [cur]
        for s in specs:
            if s.startswith('+') and not lease:
                bad.append('a forced refspec (+)')
            s = s.lstrip('+')
            dst = s.split(':', 1)[1] if ':' in s else s
            if dst == '':
                bad.append('deleting a branch')
                continue
            if dst == 'HEAD':
                _, dst, _ = git('rev-parse', '--abbrev-ref', 'HEAD')
            targets.append(re.sub(r'^refs/heads/', '', dst))
    return targets, bad


def on_pre_bash(inp):
    role, sid = identity(inp.get('session_id', ''))
    if role != 'cloud':
        return {}
    cmd = (inp.get('tool_input') or {}).get('command', '')
    if re.search(r'\bgh\s+pr\s+merge\b', cmd) or re.search(r'\bgh\s+api\b[^\n;&|]*?/merge\b', cmd):
        return deny('pre-bash', 'Cloud sessions never merge PRs; the coordinator does after verifying.')
    if re.search(CFG.get('deployPattern', r'\bvercel\b|\bdeploy\.sh\b|\bfly deploy\b|\bwrangler deploy\b'), cmd):
        return deny('pre-bash', 'Cloud sessions never deploy; the coordinator deploys from its main checkout.')
    if re.search(r'coord\.py\s+release|\.claude/bin/release', cmd):
        return deny('pre-bash', 'Only the coordinator releases claims.')
    targets, bad = push_targets(cmd)
    if bad:
        return deny('pre-bash', 'Refused: ' + '; '.join(sorted(set(bad))) + '.')
    if not targets:
        return {}
    mine = [c for c in claims() if c['session'] == sid]
    own = {c.get('Work-Branch') for c in mine}
    for t in targets:
        if t in ('main', 'master'):
            return deny('pre-bash', 'Never push main: open a PR from your work branch; the coordinator merges.')
        if t.startswith('claim/'):
            return deny('pre-bash', 'Claim branches are written by .claude/bin/claim only.')
        if t not in own:
            return deny('pre-bash', f'{t} is not your work branch (yours: {", ".join(sorted(b for b in own if b)) or "none — claim first"}).')
    return {}


def on_stop(inp):
    role, sid = identity(inp.get('session_id', ''))
    if role != 'cloud':
        return {}
    count = os.path.join(STATE, f'stop-{sid}')
    try:
        n = int(open(count).read())
    except (OSError, ValueError):
        n = 0
    if n >= 3:
        return {}
    mine = [c for c in claims(0) if c['session'] == sid]
    why = []
    _, dirty, _ = git('status', '--porcelain', '--untracked-files=no')
    if dirty:
        why.append('uncommitted changes: commit them')
    for c in mine:
        b = c.get('Work-Branch')
        if not b:
            continue
        code, ahead, _ = git('rev-list', '--count', f'origin/{b}..{b}')
        if code != 0 or ahead != '0':
            why.append(f'{b} is not pushed: git push -u origin {b}')
        owner = REPO.split('/')[0]
        code, prs, _ = run('gh', 'api', f'repos/{REPO}/pulls?head={owner}:{b}&state=all', '-q', 'length', cwd=ROOT)
        if code == 0 and prs.strip() == '0':
            why.append(f'no PR for {b}: open one (gh api repos/{REPO}/pulls -f head={b} -f base=main ...), '
                       f"then .claude/bin/ready {c['issue']} <pr>")
    if not why:
        return {}
    open(count, 'w').write(str(n + 1))
    return {'decision': 'block', 'reason': 'Before you stop (docs/agents/CLOUD.md): ' + '; '.join(why)}


# --- claim / release / list -----------------------------------------------------------------------

def gh_best_effort(*a):
    code, _, err = run('gh', 'api', *a, cwd=ROOT)
    if code:
        log('gh api failed: ' + ' '.join(a[:2]) + ' ' + err)


def cmd_claim(args):
    import argparse
    ap = argparse.ArgumentParser(prog='claim')
    ap.add_argument('issue', type=int)
    ap.add_argument('--branch')
    ap.add_argument('--touches', nargs='+', action='extend', default=[])
    ap.add_argument('--title', default='')
    ap.add_argument('--session', help='(local only) whose claim this is; default: the coordinator')
    o = ap.parse_args(args)
    role, sid = identity()
    if o.session and role != 'cloud':
        sid = norm(o.session)
        role = 'cloud' if not re.match(r'^[0-9a-f-]{36}$', sid) else role
    elif role == 'local' and not sid and os.environ.get('MMK_CREW_SESSION'):
        sid = norm(os.environ['MMK_CREW_SESSION'])
    elif role == 'local' and not sid:
        try:
            sid = norm(open(os.path.join(STATE, 'coordinator')).read())
            role = 'coordinator'
        except OSError:
            sys.exit('claim: no session id (set CLAUDE_CODE_REMOTE_SESSION_ID or pass --session)')
    cs = claims(0)
    have = next((c for c in cs if c['issue'] == o.issue), None)
    if have and have['session'] != sid:
        sys.exit(f"claim: #{o.issue} is held by {have.get('Claim-Session')} on {have.get('Work-Branch')}. "
                 f'Comment "blocked: #{o.issue} is taken" on your issue and stop, or ask the coordinator.')
    touches = list(dict.fromkeys((have['touches'] if have else []) + o.touches))
    branch = o.branch or (have and have.get('Work-Branch'))
    if not branch or not touches:
        sys.exit('claim: give --branch and at least one --touches path[#symbol]')
    others = [c for c in cs if c['issue'] != o.issue]
    if not have and role == 'cloud' and sum(c.get('Claim-Role') == 'cloud' for c in others) >= CFG['maxCloud']:
        sys.exit(f"claim: {CFG['maxCloud']} cloud claims are open already; wait for one to be merged.")
    warn = []
    for t in touches:
        f, _, sym = t.partition('#')
        for c in others:
            for u in c['touches']:
                g, _, usym = u.partition('#')
                same = f == g or covers(u, f) or covers(t, g)
                if not same:
                    continue
                if sym and usym and sym == usym:
                    sys.exit(f"claim: {t} is held by #{c['issue']} ({c.get('Claim-Session')}). Wait for it, or ask the coordinator.")
                if f in CFG['hot'] and (not sym or not usym):
                    sys.exit(f"claim: {f} is a hot file and #{c['issue']} holds it ({u}); name the symbols you will change "
                             f"(--touches {f}#name), or wait.")
                warn.append((c['issue'], f))
    _, base, _ = git('rev-parse', '--short', 'origin/main')
    title = o.title or (have and have['title'].split(' — ', 1)[-1]) or f'issue {o.issue}'
    msg = f"claim #{o.issue} — {title}\n\nClaim-Session: {link(sid)}\nClaim-Role: {role if role != 'local' else 'local'}\n" \
          f"Work-Branch: {branch}\nBase: {base}\n" + ''.join(f'Touches: {t}\n' for t in touches)
    parent = ['-p', have['sha']] if have else []
    # The claim commit carries main's tree, not an empty one: a branch-form claim (cloud fallback) then still has
    # the project's own deploy settings (e.g. web/vercel.json deploymentEnabled), so hosts that build every branch
    # skip it instead of failing a build that still counts against their daily quota (Vercel, 11/3: 34 of 100).
    _, tree, _ = git('rev-parse', 'origin/main^{tree}')
    code, sha, err = run('git', 'commit-tree', tree.strip() or EMPTY_TREE, *parent, cwd=ROOT, inp=msg)
    if code:
        sys.exit('claim: ' + err)
    # refs/claims/issue-N first (no branch hooks fire). Cloud git proxies only accept pushes to branches, so if the
    # ref push is refused there, fall back to the old branch form claim/issue-N; readers accept both.
    ref = f'refs/claims/issue-{o.issue}'
    lease = [] if have else [f'--force-with-lease={ref}:']
    code, _, err = git('push', '-q', *lease, 'origin', f'{sha}:{ref}')
    if code == 0:  # move an old branch claim over: drop the branch so it stops triggering branch hooks
        git('push', '-q', 'origin', f':refs/heads/claim/issue-{o.issue}')
    else:
        log(f'claim #{o.issue}: refs/claims push refused ({err.strip()[:120]}), using branch claim/issue-{o.issue}')
        ref = f'refs/heads/claim/issue-{o.issue}'
        lease = [] if have else [f'--force-with-lease={ref}:']
        code, _, err = git('push', '-q', *lease, 'origin', f'{sha}:{ref}')
    if code:
        sys.exit(f'claim: lost the race or rejected — someone else may have just claimed #{o.issue}.\n{err}')
    git('fetch', '-q', 'origin', f'+{ref}:refs/remotes/origin/claim/issue-{o.issue}')
    if not have:
        owner = 'owner:cloud' if role == 'cloud' else 'owner:local'
        gh_best_effort('-X', 'POST', f'repos/{REPO}/issues/{o.issue}/labels', '-f', f'labels[]={owner}')
        status(o.issue, 'status:in-progress')
    claim_comment(o.issue, sid, role, branch, base, touches, warn, widened=bool(have))
    print(f'claimed #{o.issue} on {branch}: ' + ', '.join(touches))
    for other, f in sorted(set(warn)):
        print(f'note: shares {f} with #{other} (different symbols: fine, but rebase onto main often)')


CLAIM_MARK = '<!-- coord:claim -->'


def claim_comment(n, sid, role, branch, base, touches, warn, widened):
    """One claim comment per issue, edited in place when the claim widens (10-29: a new comment per widening, each
    listing every symbol pair on a shared file, grew to 9,000 characters). Overlaps: one line per other issue and file."""
    shares = {}
    for (other, f) in warn:
        shares.setdefault(other, set()).add(f)
    lines = [f"{CLAIM_MARK}\n🔒 claimed by {link(sid)} ({role}){' · widened ' + time.strftime('%H:%M UTC', time.gmtime()) if widened else ''}",
             f"- branch: `{branch}`  base: main {base}"]
    if len(touches) <= 4:
        lines.append('- touches: ' + ', '.join(f'`{t}`' for t in touches))
    else:
        lines.append(f'<details><summary>touches ({len(touches)})</summary>\n\n' + '\n'.join(f'- `{t}`' for t in touches) + '\n</details>')
    if shares:
        lines.append('- shares files (different symbols) with: ' + '; '.join(f"#{k} in {', '.join(sorted('`' + x + '`' for x in v))}" for k, v in sorted(shares.items())))
    body = '\n'.join(lines)
    code, ids, _ = run('gh', 'api', f'repos/{REPO}/issues/{n}/comments?per_page=100', '--jq',
                       f'[.[]|select((.body|contains("{CLAIM_MARK}")) or (.body|startswith("🔒")))|.id]|last // empty', cwd=ROOT)
    if code == 0 and ids.strip():
        code, _, err = run('gh', 'api', '-X', 'PATCH', f'repos/{REPO}/issues/comments/{ids.strip()}', '-f', f'body={body}', cwd=ROOT)
        if code == 0:
            return
        log('claim comment edit failed, posting: ' + err)
    gh_best_effort('-X', 'POST', f'repos/{REPO}/issues/{n}/comments', '-f', f'body={body}')


def cmd_release(args):
    role, _ = identity()
    if role == 'cloud':
        sys.exit('release: only the coordinator releases claims')
    for n in args:
        code, _, err = git('push', '-q', 'origin', f':refs/claims/issue-{int(n)}')
        code2, _, err2 = git('push', '-q', 'origin', f':refs/heads/claim/issue-{int(n)}')  # old branch form, if any
        print(f'released #{n}' if code == 0 or code2 == 0 else f'#{n}: {err} {err2}')
        git('update-ref', '-d', f'refs/remotes/origin/claim/issue-{int(n)}')
        status(int(n), None)


STATUSES = ('status:todo', 'status:in-progress', 'status:review')


def status(n, to):
    """one status label at a time: `to` on, the other status:* off (None: all off, for a closed issue)"""
    code, have, _ = run('gh', 'api', f'repos/{REPO}/issues/{n}/labels', '--jq', '.[].name', cwd=ROOT)
    have = have.split() if code == 0 else list(STATUSES)
    for s in STATUSES:
        if s != to and s in have:
            gh_best_effort('-X', 'DELETE', f'repos/{REPO}/issues/{n}/labels/{s}')
    if to and to not in have:
        gh_best_effort('-X', 'POST', f'repos/{REPO}/issues/{n}/labels', '-f', f'labels[]={to}')


PR_SECTIONS = ['Numbers', 'Screenshots', 'Commands and output', 'Spec conformance']  # the mmk-crew PR template
CLOSING = re.compile(r'\b(close[sd]?|fix(e[sd])?|resolve[sd]?|refs?)\s*:?\s+([\w.-]+/[\w.-]+)?#\d+', re.I)
HEADING = re.compile(r'^(#{1,6})\s+(.+?)\s*#*\s*$', re.M)


def body_problems(body, template=None, sections=None):
    """What a PR body lacks (coord.json "prBody"): a closing or Refs link to an issue, and each evidence section
    filled, by content or "none, because ...". A section the repo's own template does not have is not required.
    A table counts only with a row below its header."""
    body = re.sub(r'<!--.*?-->', '', body or '', flags=re.S)
    out = [] if CLOSING.search(body) else ['no "Closes #N" or "Refs #N"']
    names = sections or PR_SECTIONS
    if template is not None:
        have = {h.group(2).strip().lower() for h in HEADING.finditer(template)}
        names = [n for n in names if n.lower() in have]
    heads = list(HEADING.finditer(body))
    for name in names:
        i = next((i for i, h in enumerate(heads) if h.group(2).strip().lower() == name.lower()), None)
        if i is None:
            out.append(f'section "{name}" missing')
            continue
        level, end = len(heads[i].group(1)), len(body)
        for h in heads[i + 1:]:
            if len(h.group(1)) <= level:
                end = h.start()
                break
        text = body[heads[i].end():end].strip()
        rows = [r for r in text.splitlines() if r.strip().startswith('|')]
        if rows:  # a table: header, separator, then at least one row with something in it
            filled = [r for r in rows[2:] if r.replace('|', '').strip(' -:')]
            others = '\n'.join(r for r in text.splitlines() if not r.strip().startswith('|')).strip()
            if not filled and not others:
                out.append(f'section "{name}" has an empty table')
        elif not text:
            out.append(f'section "{name}" empty (content, or "none, because ...")')
    return out


BUG_SECTION = 'Before and after'  # a [Bug] PR: the reproducing test failing before the fix, passing after
TESTISH = re.compile(r'(^|/)(tests?|__tests__|e2e|spec|testdata|fixtures?)/|_test\.\w+$|\.(test|spec)\.\w+$|(^|/)test_[^/]*\.py$', re.I)
DOCISH = re.compile(r'(^|/)docs?/|\.(md|mdx|txt|png|jpe?g|gif|webp)$', re.I)


def bug_order(pr):
    """A bug PR commits the failing test first, alone, then the fix: a commit that touches tests and no code must come
    before the first commit that touches code (docs and images count as neither). '' when it does, else the problem."""
    code, out, _ = run('gh', 'api', f'repos/{REPO}/pulls/{pr}/commits?per_page=100', '--jq', '.[].sha', cwd=ROOT)
    if code or not out.strip():
        return ''  # unreadable: say nothing rather than guess
    test_first = False
    for sha in out.split()[:30]:
        code, files, _ = run('gh', 'api', f'repos/{REPO}/commits/{sha}', '--jq', '.files[].filename', cwd=ROOT)
        if code:
            return ''
        files = [f for f in files.split('\n') if f and not DOCISH.search(f)]
        tests = [f for f in files if TESTISH.search(f)]
        if len(tests) < len(files):  # touches code
            return '' if test_first else ('bug fix: no commit with only the failing test before the fix '
                                          '(commit the test first, alone, then the fix)')
        test_first = test_first or bool(tests)
    return ''


def cmd_ready(args):
    """the worker's last step: check the PR body, status:review (and no other status) on the issue, then the
    "ready: PR #M" comment. coord.json "prBody": {"mode": "log"|"enforce", "sections": [...]}; log (the default) records
    the problems in the ready comment, enforce refuses until the body is fixed. A [Bug] issue also needs the
    "Before and after" section (when the template has it) and the failing test committed before the fix."""
    if len(args) != 2:
        sys.exit('ready: .claude/bin/ready <issue> <pr>')
    n, pr = int(args[0]), int(args[1].lstrip('#'))
    pb = CFG.get('prBody') or {}
    notes = []
    code, out, err = run('gh', 'api', f'repos/{REPO}/pulls/{pr}', cwd=ROOT)
    if code:
        log(f'ready #{n}: cannot read PR #{pr}: {err}')
    else:
        p = json.loads(out)
        try:
            template = open(os.path.join(ROOT, '.github', 'pull_request_template.md')).read()
        except OSError:
            template = None
        code, out, _ = run('gh', 'api', f'repos/{REPO}/issues/{n}', cwd=ROOT)
        issue = json.loads(out) if code == 0 else {}
        bug = any(l['name'] == 'type:bug' for l in issue.get('labels', [])) or issue.get('title', '').startswith('[Bug]')
        sections = (pb.get('sections') or PR_SECTIONS) + ([BUG_SECTION] if bug else [])
        problems = body_problems(p.get('body'), template, sections)
        if bug:
            problems += [x for x in [bug_order(pr)] if x]
        _, default, _ = run('gh', 'api', f'repos/{REPO}', '--jq', '.default_branch', cwd=ROOT)
        base = p['base']['ref']
        if default and base != default:
            notes.append(f'base is `{base}`, not `{default}`: "Closes" will not close the issue on merge')
        if problems:
            log(f"ready #{n} PR #{pr}: body check ({pb.get('mode', 'log')}): " + '; '.join(problems))
            if pb.get('mode') == 'enforce':
                sys.exit(f'ready: PR #{pr} body is missing:\n  - ' + '\n  - '.join(problems) +
                         '\nFill it (.github/pull_request_template.md; "none, because ..." where nothing applies), then run ready again.')
            notes.append('body check (log): ' + '; '.join(problems))
    status(n, 'status:review')
    body = f'ready: PR #{pr}' + ''.join(f'\n- {x}' for x in notes)
    code, _, err = run('gh', 'api', '-X', 'POST', f'repos/{REPO}/issues/{n}/comments', '-f', f'body={body}', cwd=ROOT)
    if code:
        sys.exit('ready: could not comment: ' + err)
    print(f'#{n}: status:review, commented "ready: PR #{pr}"' + ''.join(f'\n  note: {x}' for x in notes))


CLOSES = re.compile(r'\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?\s+([\w.-]+/[\w.-]+)?#(\d+)', re.I)
CLOSE_MARK = '<!-- coord:close-merged -->'


def cmd_close_merged(args):
    """Issues a merged PR closes ("Closes #N") when its base was not the default branch: GitHub closes them only on a
    merge into the default branch (epic branches, stacked PRs, a PR left on a branch that was already merged). Per open
    issue: the merge is in the default branch, or a merged PR into it names the issue → closed, the comment says how
    it got there; an open PR from that base into the default branch, or a live base with none merged yet (an epic in
    progress) → closed, the comment says how it will get there; a base that had already gone to the default branch
    before this merge, or was deleted → left open with one comment (the work went nowhere). An issue reopened after the
    merge is left alone. Looks at PRs merged in the last --days (30). Run by the post-merge hook daily; `--dry-run` shows what it would do."""
    if identity()[0] == 'cloud':
        sys.exit('close-merged: the coordinator closes issues')
    dry = '--dry-run' in args
    days = int(args[args.index('--days') + 1]) if '--days' in args else 30
    since = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() - days * 86400))
    code, default, err = run('gh', 'api', f'repos/{REPO}', '--jq', '.default_branch', cwd=ROOT)
    if code or not default:
        sys.exit('close-merged: cannot read the repo: ' + err)
    merged = []
    for page in range(1, 11):  # newest updates first; a PR is updated when (or after) it merges
        code, out, err = run('gh', 'api', f'repos/{REPO}/pulls?state=closed&sort=updated&direction=desc&per_page=100&page={page}', cwd=ROOT)
        if code:
            sys.exit('close-merged: cannot list PRs: ' + err)
        prs = json.loads(out or '[]')
        merged += [p for p in prs if p.get('merged_at') and p['merged_at'] >= since]
        if len(prs) < 100 or prs[-1]['updated_at'] < since:
            break
    into = [p for p in merged if p['base']['ref'] == default]
    done, kept = [], []
    for p in sorted(merged, key=lambda p: p['merged_at']):
        base = p['base']['ref']
        if base == default:
            continue
        for other, num in CLOSES.findall(p.get('body') or ''):
            n = int(num)
            if other and other.lower() != REPO.lower():
                continue
            code, out, _ = run('gh', 'api', f'repos/{REPO}/issues/{n}', cwd=ROOT)
            if code:
                continue
            issue = json.loads(out)
            if issue['state'] != 'open' or 'pull_request' in issue:
                continue
            _, ev, _ = run('gh', 'api', f'repos/{REPO}/issues/{n}/events?per_page=100', '--jq',
                           f'[.[]|select(.event=="reopened" and .created_at > "{p["merged_at"]}")]|length', cwd=ROOT)
            if ev.strip() not in ('', '0'):
                kept.append(f'#{n} (reopened after PR #{p["number"]} merged into {base})')
                continue
            sha = p.get('merge_commit_sha') or ''
            what = f'PR #{p["number"]} merged into `{base}` ({sha[:7]})'
            _, st, _ = run('gh', 'api', f'repos/{REPO}/compare/{default}...{sha}', '--jq', '.status', cwd=ROOT)
            carrier = next((q for q in into if q['head']['ref'] == base and q['merged_at'] >= p['merged_at']), None)
            # a PR into the default branch that links the issue (Closes/Refs #N) first, then one that only mentions it
            linked = re.compile(rf'\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?|refs?)\s*:?\s+#{n}\b', re.I)
            mention = re.compile(rf'(?<![\w/.-])#{n}\b')
            text = lambda q: (q.get('body') or '') + ' ' + q['title']
            order = sorted(into, key=lambda q: q['merged_at'])
            landed = next((q for q in order if linked.search(text(q))), None) or \
                next((q for q in order if mention.search(text(q))), None)
            if st.strip() in ('behind', 'identical'):
                how = f'which reached `{default}`' + (f' with PR #{carrier["number"]}' if carrier else '')
            elif landed:
                how = f'and the change was landed in `{default}` by PR #{landed["number"]}'
            else:
                owner = REPO.split('/')[0]
                _, out, _ = run('gh', 'api', f'repos/{REPO}/pulls?state=all&base={default}&head={owner}:{base}&per_page=100', cwd=ROOT)
                ups = json.loads(out or '[]')
                nxt = next((q for q in ups if q['state'] == 'open'), None)
                gone = next((q for q in ups if q.get('merged_at') and q['merged_at'] < p['merged_at']), None)
                alive = run('gh', 'api', f'repos/{REPO}/branches/{base}', '--jq', '.name', cwd=ROOT)[0] == 0
                if nxt:
                    how = f'and ships to `{default}` with PR #{nxt["number"]}'
                elif alive and not gone:  # an epic still in progress
                    how = f'and reaches `{default}` when `{base}` does'
                else:  # the base had already gone to the default branch (or was deleted): this merge went nowhere
                    why = f'`{base}` went to `{default}` with PR #{gone["number"]} before this merge' if gone else f'`{base}` is deleted'
                    _, seen, _ = run('gh', 'api', f'repos/{REPO}/issues/{n}/comments?per_page=100', '--jq',
                                     f'[.[]|select(.body|contains("{CLOSE_MARK}"))]|length', cwd=ROOT)
                    kept.append(f'#{n} ({what}: not in {default}; {why.replace("`", "")})')
                    if seen.strip() in ('', '0') and not dry:
                        gh_best_effort('-X', 'POST', f'repos/{REPO}/issues/{n}/comments', '-f', f'body={CLOSE_MARK}\n'
                                       f'Still open: {what}, but {why}, so the change is not in `{default}`. '
                                       f'Open a PR to `{default}` with it, or land it again.')
                    continue
            done.append(f'close #{n}: {what}, {how}')
            if not dry:
                gh_best_effort('-X', 'POST', f'repos/{REPO}/issues/{n}/comments', '-f', f'body={CLOSE_MARK}\nClosed: {what}, {how}.')
                gh_best_effort('-X', 'PATCH', f'repos/{REPO}/issues/{n}', '-f', 'state=closed', '-f', 'state_reason=completed')
                status(n, None)
                log(f'close-merged: #{n} {what}')
    print(('would: ' if dry else '') + ('\n  '.join([''] + done) if done else 'no issue to close'))
    if kept:
        print('left open:' + '\n  '.join([''] + kept))


STALE_DAYS = 7
OWN_WORK = re.compile(r'(commit|cherry-pick|revert|am|rebase)\b|(merge|pull)\b[^:]*: Merge made')


def process_cwds():
    """Real paths that running processes use as their working directory; None when they cannot be read."""
    if os.path.isdir('/proc/self/cwd'):  # Linux
        out = set()
        for pid in os.listdir('/proc'):
            if pid.isdigit():
                try:
                    out.add(os.path.realpath(os.readlink(f'/proc/{pid}/cwd')))
                except OSError:
                    pass
        return out or None
    try:  # macOS (and Linux without /proc): lsof exits 1 on processes it may not read, so judge by the output
        _, out, _ = run('lsof', '-n', '-d', 'cwd', '-Fn')
    except OSError:
        return None
    cwds = {os.path.realpath(line[1:]) for line in out.splitlines() if line.startswith('n/')}
    return cwds or None


def cmd_prune(args):
    """Stale branches. `--remote` (the post-merge hook, at most daily): claims on closed issues released; origin branches
    merged into main deleted; unmerged ones with no claim, no open PR and no commit for STALE_DAYS kept as
    refs/pruned/<name> on origin and deleted. `--local` (the post-merge hook, every merge): worktrees gone or clean on a merged
    branch removed; local branches merged into main deleted; unmerged ones with no origin branch and no commit for
    STALE_DAYS kept as refs/pruned/local/<name> and deleted. Never removed locally: a branch with no commit of its own
    (fresh), a worktree some process has as its working directory. `--dry-run` shows what it would do.
    Every deletion is printed (and logged locally) with its sha: `git branch <name> <sha>` brings it back."""
    if identity()[0] == 'cloud':
        sys.exit('prune: the coordinator prunes (the cloud proxy refuses branch deletion)')
    dry = '--dry-run' in args
    remote = '--remote' in args
    if remote == ('--local' in args):
        sys.exit('prune: --remote or --local')
    now = time.time()
    done, kept = [], []

    def act(what, *cmd):
        done.append(what)
        if dry:
            return
        code, _, err = git(*cmd)
        line = what + (f' FAILED {err}' if code else '')
        log('prune: ' + line)
        with open(os.path.join(STATE, 'prune.log'), 'a') as f:
            f.write(time.strftime('%Y-%m-%dT%H:%M:%S ') + line + '\n')

    def age(ref):
        _, ct, _ = git('log', '-1', '--format=%ct', ref)
        return (now - int(ct or now)) / 86400

    def merged(ref, into):
        return any(git('merge-base', '--is-ancestor', ref, b)[0] == 0 for b in into)

    def fresh(b):  # no commit of its own yet: "merged" only because main already has everything it points at
        # Created, Fast-forward (git merge --ff-only, pull), reset and rename move a branch without a commit of its own;
        # any commit, amend, merge commit, cherry-pick, revert, am or rebase entry means work. Empty reflog: not fresh.
        _, rl, _ = git('reflog', 'show', '--date=unix', '--format=%gd %gs', f'refs/heads/{b}', '--')
        entries = [m.groups() for m in re.finditer(r'^\S+@\{(\d+)\} (.*)$', rl, re.M)]
        if not entries or any(OWN_WORK.match(gs) for _, gs in entries):
            return False
        return (now - int(entries[0][0])) / 86400 <= STALE_DAYS  # newest entry first

    cwd_cache = []

    def in_use(path):  # a process (a Claude session, a shell, a dev server) works inside it; unknown counts as in use
        if not cwd_cache:
            cwd_cache.append(process_cwds())
        cwds = cwd_cache[0]
        if cwds is None:
            return True
        rp = os.path.realpath(path)
        return any(c == rp or c.startswith(rp + os.sep) for c in cwds)

    if remote:
        git('fetch', '-q', '--prune', 'origin')
        cs = claims(0)
        code, prs, _ = run('gh', 'api', f'repos/{REPO}/pulls?state=open&per_page=100', '--jq', '.[].head.ref', cwd=ROOT)
        if code:
            sys.exit('prune: cannot list open PRs; nothing deleted')
        held = {c.get('Work-Branch') for c in cs} | set(prs.split())
        for c in cs:
            code, state, _ = run('gh', 'api', f"repos/{REPO}/issues/{c['issue']}", '--jq', '.state', cwd=ROOT)
            if code == 0 and state == 'closed':
                done.append(f"release #{c['issue']} (issue closed)")
                if not dry:
                    cmd_release([str(c['issue'])])
        _, refs, _ = git('for-each-ref', '--format=%(refname:short) %(objectname)', 'refs/remotes/origin/')
        for line in refs.splitlines():
            ref, sha = line.split()
            b = ref.removeprefix('origin/')
            if b in ('main', 'HEAD', 'origin') or b.startswith('claim/'):
                continue
            if b in held:
                kept.append(f'origin/{b} (claim or open PR)')
            elif merged(ref, ['origin/main']):
                act(f'delete origin/{b} {sha} (merged)', 'push', '-q', 'origin', '--delete', b)
            elif age(ref) > STALE_DAYS:
                act(f'delete origin/{b} {sha} (unmerged, {age(ref):.0f} days, kept as refs/pruned/{b} on origin)',
                    'push', '-q', 'origin', f'{sha}:refs/pruned/{b}', f':refs/heads/{b}')
            else:
                kept.append(f'origin/{b} (unmerged, {age(ref):.0f} days)')
    else:
        into = ['main', 'origin/main']
        git('worktree', 'prune')
        _, wt, _ = git('worktree', 'list', '--porcelain')
        busy = set()
        for block in wt.split('\n\n')[1:]:  # (the first is the main checkout)
            path = re.search(r'^worktree (.+)$', block, re.M).group(1)
            m = re.search(r'^branch refs/heads/(.+)$', block, re.M)
            head = m.group(1) if m else re.search(r'^HEAD (\w+)$', block, re.M).group(1)
            _, dirty, _ = run('git', 'status', '--porcelain', '--untracked-files=no', cwd=path)
            # a detached worktree is someone's pinned checkout (a render, a probe): never ours to remove
            used = False
            if m and not dirty and merged(head, into) and not fresh(head):
                used = in_use(path)
                if not used:
                    act(f'remove worktree {path} ({head}, merged, clean)', 'worktree', 'remove', path)
                    continue
            busy.add(head)
            why = ', uncommitted changes' if dirty else ', in use' if used else ''
            kept.append(f'worktree {path} ({head}{why})')
        _, cur, _ = git('branch', '--show-current')
        _, refs, _ = git('for-each-ref', '--format=%(refname:short) %(objectname)', 'refs/heads/')
        for line in refs.splitlines():
            b, sha = line.split()
            if b in ('main', cur) or b in busy:
                continue
            if merged(b, into) and not fresh(b):
                act(f'delete {b} {sha} (merged)', 'branch', '-D', b)
            elif git('rev-parse', '-q', '--verify', f'refs/remotes/origin/{b}')[0] and age(b) > STALE_DAYS:
                if not dry:
                    git('update-ref', f'refs/pruned/local/{b}', sha)
                act(f'delete {b} {sha} (unmerged, {age(b):.0f} days, kept as refs/pruned/local/{b})', 'branch', '-D', b)
            else:
                kept.append(f'{b} (unmerged, {age(b):.0f} days)')

    print(('would: ' if dry else '') + ('\n  '.join([''] + done) if done else 'nothing to prune'))
    if kept:
        print('kept:' + '\n  '.join([''] + kept))


def gh_pages(path, pages=20):
    """every item of a list endpoint (100 per page); None when a page cannot be read"""
    out = []
    for page in range(1, pages + 1):
        code, body, err = run('gh', 'api', f"{path}{'&' if '?' in path else '?'}per_page=100&page={page}", cwd=ROOT)
        if code:
            log(f'gh api {path} page {page}: {err}')
            return None
        items = json.loads(body or '[]')
        out += items
        if len(items) < 100:
            return out
    return out


def cmd_labels(args):
    """Status labels match the issue state (the post-merge hook runs it daily). Closed issue: every `status:*` removed
    (a closed card stays in Done on the board). Open issue with no `status:*`: `status:in-progress` if it is claimed,
    else `status:todo`. Open issues without a `type:*` label are listed, not changed. `--dry-run` shows what it would do."""
    if identity()[0] == 'cloud':
        sys.exit('labels: the coordinator tidies labels')
    dry = '--dry-run' in args
    names = gh_pages(f'repos/{REPO}/labels')
    if names is None:
        sys.exit('labels: cannot read the repo labels')
    statuses = sorted(l['name'] for l in names if l['name'].startswith('status:'))
    done, notes = [], []

    def act(what, *call):
        done.append(what)
        if not dry:
            gh_best_effort(*call)
            log('labels: ' + what)

    for st in statuses:
        closed = gh_pages(f'repos/{REPO}/issues?state=closed&labels={st}') or []
        for i in closed:
            act(f'#{i["number"]} closed: remove {st}', '-X', 'DELETE', f'repos/{REPO}/issues/{i["number"]}/labels/{st}')
    open_ = gh_pages(f'repos/{REPO}/issues?state=open')
    if open_ is None:
        sys.exit('labels: cannot list open issues')
    open_ = [i for i in open_ if 'pull_request' not in i]
    claimed = {c['issue'] for c in claims(3600)} if fetch_claims(0) else None  # (claims() reuses this fetch)
    missing = [s for s in ('status:todo', 'status:in-progress') if s not in statuses]
    untyped = []
    for i in open_:
        have = [l['name'] for l in i['labels']]
        if not any(l.startswith('type:') for l in have):
            untyped.append(f'#{i["number"]}')
        if any(l.startswith('status:') for l in have):
            continue
        if missing:
            notes.append(f'#{i["number"]} has no status (labels {", ".join(missing)} missing: ~/.mmk-crew/scripts/labels.sh {REPO})')
        elif claimed is None:
            notes.append(f'#{i["number"]} has no status (claims unreadable: not guessing todo or in-progress)')
        else:
            to = 'status:in-progress' if i['number'] in claimed else 'status:todo'
            act(f'#{i["number"]} open: add {to}', '-X', 'POST', f'repos/{REPO}/issues/{i["number"]}/labels', '-f', f'labels[]={to}')
    if untyped:
        notes.append(f'open issues without a type:* label ({len(untyped)}): ' + ' '.join(untyped))
    print(('would: ' if dry else '') + ('\n  '.join([''] + done) if done else 'labels in order'))
    for n in notes:
        print('note: ' + n)


def main():
    a = sys.argv[1:]
    if a[:1] == ['hook']:
        try:
            inp = json.load(sys.stdin) if not sys.stdin.isatty() else {}
            out = {'session-start': on_session_start, 'pre-bash': on_pre_bash,
                   'pre-edit': on_pre_edit, 'stop': on_stop}[a[1]](inp)
            if out:
                print(json.dumps(out))
        except Exception as e:  # fail open: a broken hook must not stop work
            log(f'hook {a[1:2]} error: {e!r}')
        return
    if a[:1] == ['claim']:
        return cmd_claim(a[1:])
    if a[:1] == ['release']:
        return cmd_release(a[1:])
    if a[:1] == ['list']:
        return print(describe(claims(0)))
    if a[:1] == ['ready']:
        return cmd_ready(a[1:])
    if a[:1] == ['labels']:
        return cmd_labels(a[1:])
    if a[:1] == ['prune']:
        return cmd_prune(a[1:])
    if a[:1] == ['close-merged']:
        return cmd_close_merged(a[1:])
    if a[:1] == ['coordinator']:
        # register the coordinator (the owner's local session): its id, or the newest local session's identity
        sid = norm(a[1]) if a[1:] else ''
        if not sid:
            ids = sorted((os.path.getmtime(os.path.join(STATE, f)), f) for f in os.listdir(STATE) if f.startswith('identity-'))
            for _, f in reversed(ids):
                d = json.load(open(os.path.join(STATE, f)))
                if d.get('role') != 'cloud' and d.get('session'):
                    sid = d['session']; break
        if not sid:
            return print('no session id: pass one (the SessionStart context prints it)')
        open(os.path.join(STATE, 'coordinator'), 'w').write(sid + '\n')
        return print('coordinator:', sid)
    print(__doc__)


if __name__ == '__main__':
    main()
