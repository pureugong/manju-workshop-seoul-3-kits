#!/usr/bin/env python3
"""Check and package the workshop kits. Used by scripts/publish-kits.py.

usage:
  python3 build.py check                    scan README.md and every kit folder, exit 1 on anything that must not be public
  python3 build.py zip <out> <tag>           check, then write <out>/<kit>.zip for each kit folder present
                                              (each zip holds <kit>/... and <kit>/VERSION = <tag>) and <out>/NOTES.md

These are the public rules (safe to publish with the release repository later, when a release workflow is added).
scripts/publish-kits.py imports this file and adds its private rules (hosts that must not be written here) on top.
"""
import os
import re
import sys
import zipfile

KITS = ["setup-check", "cleanup"]           # kit folders, in release order
REPO = os.environ.get("GITHUB_REPOSITORY", "pureugong/manju-workshop-seoul-3-kits")
ALLOWED_EXT = {".md", ".sh", ".ps1", ".txt"}
TITLES = {"setup-check": "준비물 점검", "cleanup": "실습 정리(AWS 내리고 로그아웃)"}

# (name, regex). A match anywhere in a published file stops the run.
RULES = [
    ("IPv4 address", r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])"),
    ("12-digit number (AWS account?)", r"(?<!\d)\d{12}(?!\d)"),
    ("AWS access key", r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    ("GitHub token", r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"),
    ("API key", r"\bsk-(?:ant-)?[A-Za-z0-9_-]{20,}|\bxox[abps]-[A-Za-z0-9-]{10,}"),
    ("private key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ("password value", r"(?i)(?:password|passwd|pwd|비밀번호)\s*[:=]\s*[\"']?[A-Za-z0-9!@#$%^&*_+-]{6,}"),
    ("email address", r"[A-Za-z0-9._%+-]+@(?!example\.com\b|users\.noreply\.github\.com\b)[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    ("user home folder", r"(?i)(?:/Users/|/home/|C:\\\\?Users\\\\?)(?!<|\$|%|you|student|runner|\{)[A-Za-z0-9._-]+"),
    ("placeholder", r"\[확인 ?필요|\bTODO\b(?!\(#\d+\))|\bFIXME\b|\bTBD\b|\bXXX\b"),
]
# Text that looks like a match but is fine.
ALLOW = [r"127\.0\.0\.1", r"0\.0\.0\.0"]


def published(root):
    """README.md and every file in the kit folders that exist, relative to root."""
    files = ["README.md"] if os.path.isfile(os.path.join(root, "README.md")) else []
    for kit in KITS:
        for base, dirs, names in os.walk(os.path.join(root, kit)):
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))
            files += [os.path.relpath(os.path.join(base, n), root) for n in sorted(names) if not n.startswith(".")]
    return sorted(files)


def kits_in(root):
    return [k for k in KITS if os.path.isdir(os.path.join(root, k))]


def scan(root, files, rules=RULES, allowed_ext=ALLOWED_EXT):
    problems = []
    for f in files:
        ext = os.path.splitext(f)[1]
        if ext not in allowed_ext:
            problems.append(f"{f}: 공개하지 않는 파일 형식({ext or '확장자 없음'})")
            continue
        with open(os.path.join(root, f), encoding="utf-8-sig") as fh:
            lines = fh.read().splitlines()
        for n, line in enumerate(lines, 1):
            for a in ALLOW:
                line = re.sub(a, "", line)
            for name, rx in rules:
                m = re.search(rx, line)
                if m:
                    problems.append(f"{f}:{n}: {name}: {m.group(0)[:40]}")
    return problems


def check(root):
    files = published(root)
    if not kits_in(root):
        sys.exit("키트 폴더가 없습니다")
    problems = scan(root, files)
    for f in files:
        print(f"  {f}")
    if problems:
        print("멈춤, 공개하면 안 되는 내용:")
        for p in problems:
            print(f"  {p}")
        sys.exit(1)
    print(f"검사: 이상 없음 ({len(files)}개 파일, 규칙 {len(RULES)}개)")


def build_zips(root, out, tag):
    if not re.fullmatch(r"seoul-3-v\d+", tag):
        sys.exit("태그는 seoul-3-v1 처럼 씁니다")
    os.makedirs(out, exist_ok=True)
    made = []
    for kit in kits_in(root):
        z = os.path.join(out, f"{kit}.zip")
        with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in published(root):
                if f.startswith(kit + os.sep):
                    zf.write(os.path.join(root, f), f.replace(os.sep, "/"))
            zf.writestr(f"{kit}/VERSION", tag + "\n")
        print(f"{kit}.zip:", ", ".join(zipfile.ZipFile(z).namelist()))
        made.append(kit)
    lines = [f"만쥬 워크샵 IN SEOUL 3회 키트 {tag}.", ""]
    lines += [f"- {k}.zip: {TITLES.get(k, k)}" for k in made]
    lines += ["", "이 판으로 고정한 주소:"]
    lines += [f"- https://github.com/{REPO}/releases/download/{tag}/{k}.zip" for k in made]
    with open(os.path.join(out, "NOTES.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return made


def main():
    root = os.getcwd()
    if len(sys.argv) == 2 and sys.argv[1] == "check":
        check(root)
    elif len(sys.argv) == 4 and sys.argv[1] == "zip":
        check(root)
        build_zips(root, sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
