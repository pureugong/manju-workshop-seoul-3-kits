#!/usr/bin/env bash
# 만쥬 워크샵 IN SEOUL 준비물 점검 (Mac). 이 스크립트는 아무것도 설치하거나 바꾸지 않습니다.
#
#   bash check.sh          마지막 점검: 표와 판정만 보여 줍니다
#   bash check.sh --plan   설치 모드 연습: 무엇을 어떻게 설치할지만 보여 줍니다(실제로 설치하지 않음)
#
# 실제 설치는 Claude(또는 Codex)가 setup-check.md 를 읽고 여러분 동의를 받아 하나씩 합니다.
# 준비물 목록은 아래 data 부분에 있고, 강사 저장소의 requirements.yaml 에서 만들어집니다.

set -u
MODE=check
[ "${1:-}" = "--plan" ] && MODE=plan

# >>> prep-sync:data (generated from requirements.yaml; do not edit by hand)
TOOLS=(
  'claude|Claude 계정과 앱|install|required|2.1.234|||https://claude.com/download 에서 Mac 용을 받아 응용 프로그램 폴더로 옮깁니다. 이미 있으면 Claude 메뉴의 「업데이트 확인…」|Claude 계정(Pro 이상)으로 앱에 로그인|05-claude-app.md|||'
  'github|GitHub 가입|account|required|||gh auth status||https://github.com/signup 에서 가입하고 이메일 인증|06-github-signup.md|GitHub 가입과 이메일 인증을 마치셨나요?||'
  'git|Git|install|required|2.0.0|git --version||xcode-select --install (Apple 의 설치 창이 뜨면 사람이 「설치」를 누름)|Windows 는 git config --global user.name, user.email 두 줄|07-git.md|||'
  'gh|GitHub CLI(gh)|install|required|2.0.0|gh --version|gh auth status|Homebrew 가 있으면 brew install gh. 없으면 https://github.com/cli/cli/releases/latest 의 gh_<버전>_macOS_<arm64 또는 amd64>.zip 에서 bin/gh 를 ~/.local/bin 에 넣기|설치(Homebrew 나 winget 이 없으면 설치 파일을 사람이 실행)|08-github-cli.md||gh auth login --web 로그인(8자리 코드를 브라우저에 넣고 Authorize)|'
  'node|Node.js LTS|install|required|20.9.0|node -v||https://nodejs.org/dist/index.json 에서 lts 가 false 가 아닌 가장 위 버전의 node-<버전>.pkg 를 https://nodejs.org/dist/<버전>/ 에서 받아 open 으로 열기(관리자 비밀번호는 사람이 입력)|설치 창의 비밀번호와 「예」는 사람이 누름|09-nodejs.md|||'
  'aws|AWS 가입|account|required|||aws sts get-caller-identity --profile mini-th||새 계정 가입(유료 플랜 추천), 카드와 문자 인증. 그다음 점검 때 Claude 가 AWS CLI 로그인까지 마침(서울 지역, 가입한 루트 계정으로 브라우저에서 승인만)|10-aws-signup.md|AWS 계정 가입(카드와 문자 인증까지)을 마치셨나요?||yes'
  'aws-cli|AWS CLI|install|required|2.32.0|aws --version||curl -o AWSCLIV2.pkg https://awscli.amazonaws.com/AWSCLIV2.pkg 로 받아 open AWSCLIV2.pkg 로 열기(관리자 비밀번호는 사람이 입력)|설치 창의 비밀번호와 「예」는 사람이 누름|11-aws-cli.md|||'
  'docker|Docker Desktop|install|required||docker version --format "{{.Server.Version}}"||사람이 직접 설치(Claude 는 설치하지 않음). https://www.docker.com/products/docker-desktop/ 에서 Download for Mac(Apple 칩 또는 Intel 칩)을 받아 Docker.dmg 를 열고 고래 아이콘을 응용 프로그램 폴더로 끌어다 놓기|Docker Desktop 을 받아 직접 설치하고, 다시 시작한 뒤 한 번 열어 약관 Accept(로그인은 건너뛰어도 됨), 고래 아이콘이 멈출 때까지 기다리기|12-docker.md|||'
  'cloudflare|Cloudflare 가입|account|required|||||https://dash.cloudflare.com/sign-up 에서 무료 가입하고 이메일 인증|13-cloudflare.md|Cloudflare 무료 가입과 이메일 인증을 마치셨나요?|미리 만들어도 됨(선택, 비밀번호 관리자에 안전하게 보관, 만료일 11/16, 이름에 manju-1115), 안 만들었으면 강의 당일 같이: 하루용 Workers AI 토큰과 Account ID|'
  'grafana|Grafana Cloud 가입|account|required|||||https://grafana.com 에서 무료(Free) 가입하고 이메일 인증. 가입 뒤 「Set up your first Grafana stack」 화면의 Deployment region 은 Japan(기본값) 그대로 두고 Finish Setup(한국은 목록에 없어요, 실습에서 앱 로그를 Grafana 로 보내 분석해요)|14-grafana.md|Grafana Cloud 무료 가입과 이메일 인증을 마치셨나요?|미리 만들어도 됨(선택, 비밀번호 관리자에 안전하게 보관, 만료일 11/16, 이름에 manju-1115), 안 만들었으면 강의 당일 같이: Grafana 토큰과 로그 보내기 설정|'
)
# <<< prep-sync:data

# a >= b ? (숫자 세 칸까지 비교)
ver_ge() {
  local a b i x y
  IFS=. read -r -a a <<<"$1"
  IFS=. read -r -a b <<<"$2"
  for i in 0 1 2; do
    x=${a[$i]:-0}; y=${b[$i]:-0}
    x=${x//[!0-9]/}; y=${y//[!0-9]/}
    x=${x:-0}; y=${y:-0}
    if ((10#$x > 10#$y)); then return 0; fi
    if ((10#$x < 10#$y)); then return 1; fi
  done
  return 0
}

first_version() { grep -Eo '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -n 1; }

# Claude 앱 안에서 돌면 Claude Code 가 자기 버전을 환경 변수에 남깁니다(예: claude-code_2-1-319_agent)
claude_version() {
  local v=""
  if [[ "${AI_AGENT:-}" =~ claude-code_([0-9]+)-([0-9]+)-([0-9]+) ]]; then
    v="${BASH_REMATCH[1]}.${BASH_REMATCH[2]}.${BASH_REMATCH[3]}"
  elif [ -n "${CLAUDE_CODE_EXECPATH:-}" ]; then
    v=$(printf '%s' "$CLAUDE_CODE_EXECPATH" | first_version)
  fi
  printf '%s' "${v}"
}

# 로그인 확인 명령이 있고, 그 프로그램이 있고, 성공하면 참
logged_in() {
  [ -n "$1" ] || return 1
  command -v "${1%% *}" >/dev/null 2>&1 || return 1
  eval "$1" >/dev/null 2>&1
}

remaining=0
manual=()
later_list=()
plan=()
rows=()

for line in "${TOOLS[@]}"; do
  IFS='|' read -r id name kind need min check login how human page ask later login_req <<<"$line"
  now="-"; result=""; fix=""
  label="${name}"
  [ "$need" = "optional" ] && label="${name} (선택)"

  if [ "$id" = "claude" ]; then
    now=$(claude_version)
    if [ -z "${now}" ]; then
      now="-"; result="직접 확인"
      fix="Claude 앱 Code 화면 입력창에 /status, Claude Code 줄이 ${min} 이상인지 봐 주세요"
      manual+=("${name}: Code 화면에서 /status 로 버전 확인")
    elif ver_ge "${now}" "${min}"; then
      result="통과"
    else
      result="버전 낮음"; fix="앱 메뉴의 「업데이트 확인…」으로 올린 뒤 새 세션에서 다시 점검"
      remaining=$((remaining + 1)); plan+=("[사람이 할 일] ${name}: 앱 메뉴의 「업데이트 확인…」")
    fi
  elif [ "$kind" = "install" ]; then
    prog=${check%% *}
    out=""
    if command -v "${prog}" >/dev/null 2>&1; then
      out=$(eval "${check}" 2>/dev/null)
    fi
    v=$(printf '%s' "$out" | first_version)
    if ! command -v "${prog}" >/dev/null 2>&1; then
      result="설치 필요"; fix="「${name}」 준비물 페이지, 또는 AI 에게 설치 모드를 맡겨 주세요"
      if [ "$id" = "docker" ]; then
        fix="공식 페이지에서 받아 직접 설치해 주세요(「${name}」 준비물 페이지)"
        plan+=("[사람이 할 일] ${name}: ${how}")
      else
        plan+=("[설치 예정] ${name}: ${how}")
      fi
    elif [ "$id" = "docker" ] && [ -z "${v}" ]; then
      now="설치됨"; result="켜기 필요"; fix="Docker Desktop 을 켜고 고래 아이콘이 멈추면 다시 점검"
      plan+=("[사람이 할 일] ${name}: 앱을 켜고 고래 아이콘이 멈출 때까지 기다리기")
    elif [ -z "${v}" ]; then
      now="?"; result="직접 확인"; fix="\`${check}\` 결과를 봐 주세요"
      manual+=("${name}: \`${check}\` 결과 확인")
    else
      now="${v}"
      if [ -z "${min}" ] || ver_ge "${v}" "${min}"; then
        result="통과"
      else
        result="버전 낮음"; fix="${min} 이상으로 올리기. 「${name}」 준비물 페이지"
        plan+=("[업그레이드 예정] ${name} ${v} → ${min} 이상: ${how}")
      fi
    fi
    if [ "${result}" != "통과" ] && [ "${result}" != "직접 확인" ] && [ "$need" = "required" ]; then
      remaining=$((remaining + 1))
    fi
    # 설치는 미리 꼭. 로그인처럼 당일 해도 되는 부분(later)은 판정에 세지 않습니다
    if [ -n "${later}" ] && ! logged_in "${login}"; then
      later_list+=("${name}: ${later}")
    fi
  else
    # 가입은 사람만 압니다. 로그인 확인 명령이 통과하면 가입도 된 것이고, 아니면 예/아니요로 묻습니다
    if logged_in "${login}"; then
      result="통과"; now="로그인됨"
    elif [ "${login_req}" = "yes" ]; then
      # 사전 준비에서 로그인까지 마쳐야 하는 줄(AWS). 로그인은 최대 12시간이라 날이 지나면 다시 해요
      result="로그인 필요"
      fix="가입을 마쳤다면 Claude 가 로그인을 돌려 드려요(브라우저에서 승인만). 가입 전이면 회원가입 먼저"
      [ "$need" = "required" ] && remaining=$((remaining + 1))
      plan+=("[로그인] ${name}: Claude 가 로그인을 돌리고 여러분은 브라우저에서 승인")
    else
      result="직접 확인"; fix="${ask}"
      [ -n "${later}" ] && fix="${fix} 나머지는 강의 당일 같이 해요(아직 안 돼 있어도 정상)"
      manual+=("${name}: ${ask} (예/아니요)")
      [ -n "${later}" ] && later_list+=("${name}: ${later}")
    fi
  fi
  [ "$need" = "optional" ] && [ "${result}" != "통과" ] && result="${result} (선택)"
  rows+=("| ${label} | ${now} | ${min:--} | ${result} | ${fix:--} |")
done

if [ "$MODE" = "plan" ]; then
  echo "설치 모드 연습 실행입니다. 아무것도 설치하지 않았습니다."
  echo
  if [ ${#plan[@]} -eq 0 ]; then
    echo "설치하거나 올릴 것이 없습니다."
  else
    for p in "${plan[@]}"; do echo "- $p"; done
  fi
  echo
fi

echo "| 도구 | 지금 버전 | 필요 버전 | 결과 | 고칠 것 |"
echo "|---|---|---|---|---|"
for r in "${rows[@]}"; do echo "$r"; done
echo
if [ ${#manual[@]} -gt 0 ]; then
  echo "사람이 직접 확인할 것:"
  for m in "${manual[@]}"; do echo "- $m"; done
  echo
fi
if [ ${#later_list[@]} -gt 0 ]; then
  echo "당일 같이 해도 되는 것(판정에 세지 않음):"
  for m in "${later_list[@]}"; do echo "- $m"; done
  echo
fi
if [ "${remaining}" -eq 0 ]; then
  echo "판정: 오늘 실습 준비 완료"
else
  echo "판정: 남은 것 ${remaining}개"
fi
