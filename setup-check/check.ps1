# 만쥬 워크샵 IN SEOUL 준비물 점검 (Windows). 이 스크립트는 아무것도 설치하거나 바꾸지 않습니다.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\check.ps1          마지막 점검: 표와 판정만
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\check.ps1 -Plan    설치 모드 연습: 무엇을 설치할지만
#
# 실제 설치는 Claude(또는 Codex)가 setup-check.md 를 읽고 여러분 동의를 받아 하나씩 합니다.
# 준비물 목록은 아래 data 부분에 있고, 강사 저장소의 requirements.yaml 에서 만들어집니다.
param([switch]$Plan)
$ErrorActionPreference = 'SilentlyContinue'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

# 설치 전에 열어 둔 창(Claude 앱 포함)은 새로 설치한 프로그램의 경로(PATH)를 모릅니다.
# 점검만큼은 정확하도록 시스템에 저장된 PATH 를 다시 읽고, 예전 창에서는 못 찾던 도구를 따로 알려 줍니다.
$oldPathDirs = @($env:Path -split ';' | Where-Object { $_ } | ForEach-Object { $_.TrimEnd('\').ToLower() })
$freshPath = @([Environment]::GetEnvironmentVariable('Path', 'Machine'), [Environment]::GetEnvironmentVariable('Path', 'User')) -join ';'
$env:Path = (@($env:Path -split ';') + @($freshPath -split ';') | Where-Object { $_ } | Select-Object -Unique) -join ';'
$restartList = @()
$hasWinget = [bool](Get-Command winget -ErrorAction SilentlyContinue)
$needWinget = $false

# >>> prep-sync:data (generated from requirements.yaml; do not edit by hand)
$Tools = @(
  'claude|Claude 계정과 앱|install|required|2.1.234|||https://claude.com/download 에서 Windows 용을 받아 실행합니다. 이미 있으면 Help 메뉴의 「업데이트 확인…」|Claude 계정(Pro 이상)으로 앱에 로그인|05-claude-app.md||||',
  'github|GitHub 가입|account|required|||gh auth status||https://github.com/signup 에서 가입하고 이메일 인증|06-github-signup.md|GitHub 가입과 이메일 인증을 마치셨나요?|||',
  'git|Git|install|required|2.0.0|git --version||winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements|Windows 는 git config --global user.name, user.email 두 줄|07-git.md|||https://api.github.com/repos/git-for-windows/git/releases/latest 의 assets 에서 Git-<버전>-64-bit.exe(ARM 은 Git-<버전>-arm64.exe) 주소를 찾아 받고 /VERYSILENT /NORESTART 로 실행(git-scm.com/downloads/win 이 내려주는 것과 같은 공식 파일, 관리자 창의 「예」는 사람이 누름)|',
  'gh|GitHub CLI(gh)|install|required|2.0.0|gh --version|gh auth status|winget install --id GitHub.cli --source winget --accept-package-agreements --accept-source-agreements|설치(Homebrew 나 winget 이 없으면 설치 파일을 사람이 실행)|08-github-cli.md||gh auth login --web 로그인(8자리 코드를 브라우저에 넣고 Authorize)|https://api.github.com/repos/cli/cli/releases/latest 의 assets 에서 gh_<버전>_windows_amd64.msi(ARM 은 arm64.msi) 주소를 찾아 받고 msiexec /i <파일> /qn /norestart 로 설치(관리자 창의 「예」는 사람이 누름)|',
  'node|Node.js LTS|install|required|20.9.0|node -v||https://nodejs.org/dist/index.json 에서 lts 가 false 가 아닌 가장 위 버전의 node-<버전>-x64.msi(ARM 은 arm64.msi)를 받아 실행하기|설치 창의 비밀번호와 「예」는 사람이 누름|09-nodejs.md||||',
  'aws|AWS 가입|account|required|||aws sts get-caller-identity --profile mini-th||새 계정 가입(유료 플랜 추천), 카드와 문자 인증. 그다음 점검 때 Claude 가 AWS CLI 로그인까지 마침(서울 지역, 가입한 루트 계정으로 브라우저에서 승인만)|10-aws-signup.md|AWS 계정 가입(카드와 문자 인증까지)을 마치셨나요?|||yes',
  'aws-cli|AWS CLI|install|required|2.32.0|aws --version||https://awscli.amazonaws.com/AWSCLIV2.msi 를 받아 실행(관리자 권한이 없으면 https://awscli.amazonaws.com/AWSCLIV2-User.msi)|설치 창의 비밀번호와 「예」는 사람이 누름|11-aws-cli.md||||',
  'docker|Docker Desktop|install|required||docker version --format "{{.Server.Version}}"||사람이 직접 설치(Claude 는 설치하지 않음, winget 이나 wsl --install 도 돌리지 않음). https://www.docker.com/products/docker-desktop/ 에서 Download for Windows 를 받아 실행하고 기본값 그대로 OK, Next, 끝나면 컴퓨터 다시 시작|Docker Desktop 을 받아 직접 설치하고, 다시 시작한 뒤 한 번 열어 약관 Accept(로그인은 건너뛰어도 됨), 고래 아이콘이 멈출 때까지 기다리기|12-docker.md||||',
  'cloudflare|Cloudflare 가입|account|required|||||https://dash.cloudflare.com/sign-up 에서 무료 가입하고 이메일 인증|13-cloudflare.md|Cloudflare 무료 가입과 이메일 인증을 마치셨나요?|미리 만들어도 됨(선택, 비밀번호 관리자에 안전하게 보관, 만료일 11/16, 이름에 manju-1115), 안 만들었으면 강의 당일 같이: 하루용 Workers AI 토큰과 Account ID||',
  'grafana|Grafana Cloud 가입|account|required|||||https://grafana.com 에서 무료(Free) 가입하고 이메일 인증. 가입 뒤 「Set up your first Grafana stack」 화면의 Deployment region 은 Japan(기본값) 그대로 두고 Finish Setup(한국은 목록에 없어요, 실습에서 앱 로그를 Grafana 로 보내 분석해요)|14-grafana.md|Grafana Cloud 무료 가입과 이메일 인증을 마치셨나요?|미리 만들어도 됨(선택, 비밀번호 관리자에 안전하게 보관, 만료일 11/16, 이름에 manju-1115), 안 만들었으면 강의 당일 같이: Grafana 토큰과 로그 보내기 설정||'
)
# <<< prep-sync:data

function Get-FirstVersion([string]$s) {
  $m = [regex]::Match($s, '[0-9]+\.[0-9]+(\.[0-9]+)?')
  if ($m.Success) { return $m.Value } else { return '' }
}

function Test-VersionAtLeast([string]$a, [string]$b) {
  $x = ($a.Split('.') + @('0', '0', '0'))[0..2] | ForEach-Object { [int]($_ -replace '[^0-9]', '' -replace '^$', '0') }
  $y = ($b.Split('.') + @('0', '0', '0'))[0..2] | ForEach-Object { [int]($_ -replace '[^0-9]', '' -replace '^$', '0') }
  for ($i = 0; $i -lt 3; $i++) {
    if ($x[$i] -gt $y[$i]) { return $true }
    if ($x[$i] -lt $y[$i]) { return $false }
  }
  return $true
}

function Get-ClaudeVersion {
  if ($env:AI_AGENT -match 'claude-code_(\d+)-(\d+)-(\d+)') { return "$($Matches[1]).$($Matches[2]).$($Matches[3])" }
  if ($env:CLAUDE_CODE_EXECPATH) { return (Get-FirstVersion $env:CLAUDE_CODE_EXECPATH) }
  return ''
}

function Invoke-Line([string]$cmd) {
  try {
    $out = Invoke-Expression "$cmd 2>&1" | Out-String
    return @{ ok = ($LASTEXITCODE -eq 0); out = $out }
  } catch { return @{ ok = $false; out = '' } }
}

function Test-LoggedIn([string]$cmd) {
  if (-not $cmd) { return $false }
  if (-not (Get-Command $cmd.Split(' ')[0] -ErrorAction SilentlyContinue)) { return $false }
  return (Invoke-Line $cmd).ok
}

$remaining = 0
$manual = @()
$laterList = @()
$planList = @()
$rows = @()

foreach ($line in $Tools) {
  $f = $line.Split('|')
  $id, $name, $kind, $need, $min, $check, $login, $how, $human, $page, $ask, $later, $alt, $loginReq = $f
  # winget 이 없는 PC(예: Windows Server)는 winget 부터 설치하고, 그것도 안 되면 목록의 공식 설치 파일로 갑니다
  if ($how -like 'winget *' -and -not $hasWinget) { $needWinget = $true; if ($alt) { $how = "$how (winget 설치가 안 되면: $alt)" } }
  $now = '-'; $result = ''; $fix = ''
  $label = $name
  if ($need -eq 'optional') { $label = "$name (선택)" }

  if ($id -eq 'claude') {
    $now = Get-ClaudeVersion
    if (-not $now) {
      $now = '-'; $result = '직접 확인'
      $fix = "Claude 앱 Code 화면 입력창에 /status, Claude Code 줄이 $min 이상인지 봐 주세요"
      $manual += "${name}: Code 화면에서 /status 로 버전 확인"
    } elseif (Test-VersionAtLeast $now $min) {
      $result = '통과'
    } else {
      $result = '버전 낮음'; $fix = '앱 메뉴의 「업데이트 확인…」으로 올린 뒤 새 세션에서 다시 점검'
      $remaining++; $planList += "[사람이 할 일] ${name}: 앱 메뉴의 「업데이트 확인…」"
    }
  } elseif ($kind -eq 'install') {
    $prog = $check.Split(' ')[0]
    $has = [bool](Get-Command $prog -ErrorAction SilentlyContinue)
    $v = ''
    if ($has) {
      $v = Get-FirstVersion (Invoke-Line $check).out
      $dir = (Split-Path (Get-Command $prog).Source -Parent).TrimEnd('\').ToLower()
      if ($oldPathDirs -notcontains $dir) { $restartList += $name }
    }
    if (-not $has) {
      $result = '설치 필요'; $fix = "「$name」 준비물 페이지, 또는 AI 에게 설치 모드를 맡겨 주세요"
      if ($id -eq 'docker') {
        $fix = "공식 페이지에서 받아 직접 설치해 주세요(「$name」 준비물 페이지)"
        $planList += "[사람이 할 일] ${name}: $how"
      } else {
        $planList += "[설치 예정] ${name}: $how"
      }
    } elseif ($id -eq 'docker' -and -not $v) {
      $now = '설치됨'; $result = '켜기 필요'; $fix = 'Docker Desktop 을 켜고 고래 아이콘이 멈추면 다시 점검'
      $planList += "[사람이 할 일] ${name}: 앱을 켜고 고래 아이콘이 멈출 때까지 기다리기"
    } elseif (-not $v) {
      $now = '?'; $result = '직접 확인'; $fix = "``$check`` 결과를 봐 주세요"
      $manual += "${name}: ``$check`` 결과 확인"
    } else {
      $now = $v
      if (-not $min -or (Test-VersionAtLeast $v $min)) { $result = '통과' }
      else {
        $result = '버전 낮음'; $fix = "$min 이상으로 올리기. 「$name」 준비물 페이지"
        $planList += "[업그레이드 예정] $name $v → $min 이상: $how"
      }
    }
    if ($result -ne '통과' -and $result -ne '직접 확인' -and $need -eq 'required') { $remaining++ }
    # 설치는 미리 꼭. 로그인처럼 당일 해도 되는 부분(later)은 판정에 세지 않습니다
    if ($later -and -not (Test-LoggedIn $login)) { $laterList += "${name}: $later" }
  } else {
    # 가입은 사람만 압니다. 로그인 확인 명령이 통과하면 가입도 된 것이고, 아니면 예/아니요로 묻습니다
    if (Test-LoggedIn $login) {
      $result = '통과'; $now = '로그인됨'
    } elseif ($loginReq -eq 'yes') {
      # 사전 준비에서 로그인까지 마쳐야 하는 줄(AWS). 로그인은 최대 12시간이라 날이 지나면 다시 해요
      $result = '로그인 필요'
      $fix = '가입을 마쳤다면 Claude 가 로그인을 돌려 드려요(브라우저에서 승인만). 가입 전이면 회원가입 먼저'
      if ($need -eq 'required') { $remaining++ }
      $planList += "[로그인] ${name}: Claude 가 로그인을 돌리고 여러분은 브라우저에서 승인"
    } else {
      $result = '직접 확인'; $fix = $ask
      if ($later) { $fix = "$fix 나머지는 강의 당일 같이 해요(아직 안 돼 있어도 정상)" }
      $manual += "${name}: $ask (예/아니요)"
      if ($later) { $laterList += "${name}: $later" }
    }
  }
  if ($need -eq 'optional' -and $result -ne '통과') { $result = "$result (선택)" }
  if (-not $min) { $minShow = '-' } else { $minShow = $min }
  if (-not $fix) { $fix = '-' }
  $rows += "| $label | $now | $minShow | $result | $fix |"
}

if ($Plan) {
  Write-Output '설치 모드 연습 실행입니다. 아무것도 설치하지 않았습니다.'
  Write-Output ''
  if ($needWinget) { Write-Output '- [먼저 설치] winget(마이크로소프트의 프로그램 설치 도구): 이 컴퓨터에 없어서 마이크로소프트 공식 winget-cli 릴리스의 설치 파일과 같은 릴리스의 의존 패키지로 먼저 깝니다. 안 되면 바로 아래 줄의 공식 설치 파일로 갑니다(방법은 setup-check.md 의 When winget is missing)' }
  if ($planList.Count -eq 0) { Write-Output '설치하거나 올릴 것이 없습니다.' }
  else { $planList | ForEach-Object { Write-Output "- $_" } }
  Write-Output ''
}

Write-Output '| 도구 | 지금 버전 | 필요 버전 | 결과 | 고칠 것 |'
Write-Output '|---|---|---|---|---|'
$rows | ForEach-Object { Write-Output $_ }
Write-Output ''
if ($manual.Count -gt 0) {
  Write-Output '사람이 직접 확인할 것:'
  $manual | ForEach-Object { Write-Output "- $_" }
  Write-Output ''
}
if ($laterList.Count -gt 0) {
  Write-Output '당일 같이 해도 되는 것(판정에 세지 않음):'
  $laterList | ForEach-Object { Write-Output "- $_" }
  Write-Output ''
}
if ($restartList.Count -gt 0) {
  Write-Output ('새로 설치해서 이 창이 아직 모르는 것: ' + ($restartList -join ', '))
  Write-Output 'Claude 앱(또는 PowerShell 창)을 완전히 종료했다가 다시 열면 Claude 도 바로 씁니다.'
  Write-Output ''
}
if ($remaining -eq 0) { Write-Output '판정: 오늘 실습 준비 완료' }
else { Write-Output "판정: 남은 것 ${remaining}개" }
