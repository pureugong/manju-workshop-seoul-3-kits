# 401 mmk-crew 적용 (2026-11-08)

공개 릴리즈 저장소에 mmk-crew 방식을 들였습니다. 이 저장소는 작아요. 파일 7개에 커밋 5개이고, 키트는 강의 저장소의 스크립트로만 들어옵니다. 그래서 가이드에서 줄여도 되는 곳은 줄였고, 그 이유를 아래에 적었습니다.

## 살펴본 것

- 기계: git, gh(로그인됨), python3, tmux, node, go, cargo 가 모두 있습니다. pwsh 는 없어서 `check.ps1` 은 Windows 시험 기계에서 봅니다.
- 저장소: 스택, 테스트, 배포 흔적이 없습니다. 이슈 0, 열린 PR 0, 오래된 브랜치 0 이고 라벨은 없었습니다.
- 공개 저장소라서 mmk-crew 가 넣는 파일 27개를 먼저 같은 규칙으로 검사했습니다. 걸린 것은 세 가지였고 모두 공개해도 되는 것이었습니다.
  - claude.ai 세션 링크 형식
  - TODO 를 막는 규칙 글자 자체
  - PR 템플릿의 일반 단어 하나

## 가이드 단계별로 한 것과 줄인 것

| 단계 | 한 것 | 줄인 것과 이유 |
|---|---|---|
| 0 기계 | survey 로 확인 | 설치할 것 없음 |
| 1 살펴보기 | survey, 파일과 공개 범위 검사 | 영역 후보는 폴더 2개뿐이라 손으로 정함 |
| 2 질문 | 한 번에 묶어 물음. 받은 답: 다운로드는 Release zip, log 모드로 시작 | 나머지(영역, 핫 파일, 10분 보고)는 추천안대로 하고 여기에 적음 |
| 3 설치 | `setup --mode log --max-cloud 1`, 라벨 8개, PR 템플릿, CLAUDE.md, docs/agents, git 훅 | `--stack` 없음(코드 스택이 없음), `--release` 없음(판은 seoul-3-vN 이고 release-please 를 쓰지 않음), `--deploy` 없음(서버 배포가 없음) |
| 3 README 와 배지 | 배지 SVG 는 `.github/badges/` 에 둠 | README 는 강의 저장소 스크립트가 쓰는 파일이라 여기서 고치지 않음. 배지 줄은 그쪽 원본에 넣어 다음 publish 로 들어옴 |
| 3 영역 표 | 4개: 준비물 점검 키트, 실습 정리 키트, Release, 첫 화면과 문서 | |
| 3 VERIFY.md | 다섯 단계를 채우고 한 번 끝까지 돌림(아래) | 서버가 없어서 「시작」은 zip 빌드로 대신함 |
| 3 RULES.md | 이 저장소 규칙 5줄(직접 고치지 않기, 공개 저장소, 태그 지우지 않기, 클라우드 금지 명령, extras) | |
| 3 Checks | `python3 .github/build.py check && bash -n setup-check/check.sh` | 타입 검사, 린트, 단위 테스트, e2e 는 해당 없음 |
| 3 deployPattern | `gh release`, `gh workflow run`, `gh repo edit --visibility`, `publish-kits.py pr/release` | |
| 3 번호 문서 | 100-overview(101), 400-devlog(401), 500-runbooks(501) | 200-guide 는 첫 화면 README 가 수강생 안내라서, 300-research 는 조사한 것이 없어서 두지 않음 |
| 3 이슈 정리, 브랜치 정리 | 할 것 없음 | 이슈 0, publish 브랜치 2개는 이미 지움 |
| 4 시험(log 모드) | 이 PR 은 log 모드 | 클라우드 세션 시험은 줄임. publish 는 로컬 스크립트로만 하고 병렬 작업이 없음. 첫 실제 작업(Actions 자동 Release)을 시험 삼아 log 를 읽음 |
| 5 enforce 와 10분 보고 | 시험 뒤 enforce 로 바꿀 예정 | 10분 보고와 코디네이터 등록은 생략. 쌓인 일이 없는 저장소라서 |

## VERIFY 첫 실행 (master befcc3f)

- `build.py zip` 결과는 「검사: 이상 없음」이고, setup-check.zip(파일 4개와 VERSION)과 cleanup.zip(파일 2개와 VERSION)이 나왔습니다.
- `bash setup-check/check.sh --plan` 의 끝 줄은 「판정: 오늘 실습 준비 완료」입니다(Mac).
- 로그인 없이 `latest` 두 주소를 받으면 200 이고, VERSION 은 seoul-3-v1 입니다.

## 정한 것

- 이 저장소는 공개입니다. 브랜치도 바로 보이니, 올리기 전에 Checks 를 돌립니다.
- 한 번 낸 판(태그)은 지우지 않습니다. 잘못 냈으면 다음 판을 냅니다.
- GitHub Actions 는 다음 PR 에서 붙입니다. 공개 저장소라 무료이고, 비공개일 때는 잡을 건너뛰게 합니다.
