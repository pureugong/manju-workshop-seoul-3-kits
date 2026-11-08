<!-- Managed by mmk-crew (copied on every setup). The release runbook skeleton for skill mmk-crew-release:
copy it into a Claude Doc per release and fill it in. The owner reads it, so the headings stay Korean
(docs/agents/KOREAN.md). Keep the log table from the first minute. -->

# 릴리즈 런북: <이름> (<YYYY-MM-DD>)

- 담당: <세션 이름> / 승인: <오너>
- 타임라인(오너와 합의): 시작 <HH:MM>, 끝 <HH:MM>, 마감 <HH:MM>
- 범위: <저장소>: PR #<n>, #<n> / <저장소>: PR #<n>

## 실행 로그

| 시각 | 단계 | 한 일 | 결과(숫자, 링크) | 판정, 다음 |
|---|---|---|---|---|
| <HH:MM> | 준비 | 런북 작성 | <링크> | 승인 대기 |

## 리뷰

| PR | 판정 | 최고 심각도 | 하위호환 근거 | PR 본문 증거 |
|---|---|---|---|---|
| <저장소>#<n> | 진행 / 보류 / 돌려보냄 | 없음 / 낮음 / 높음 / 치명 | 호출자 검색 결과, Make, CLI 동작 | 문제, 요청, 변경, 증거 |

## 사전 기준값

| 항목 | 값 | 잰 시각 |
|---|---|---|
| 오류율 | | |
| 엣지 함수 오류 | | |
| cron 성공 수 | | |
| 보안 advisor | | |
| 바뀔 객체의 지금 상태(권한, 함수 버전, active_version, 웹 배포 ID, 이미지 digest) | | |

## 단계

위험 낮은 순서: 문서, 운영 DB, 서버 코드와 함수, 고객 이미지.

| # | 할 일 | 10분 확인 | 관찰 | 통과 기준 | 롤백 | 승인 |
|---|---|---|---|---|---|---|
| 0 | <사전 수정> | | | | | 필요 없음 |
| 1 | <문서 PR 머지> | | | | revert | 필요 없음 |
| 2 | <운영 DB 변경> | 권한, 오류 로그 | 30분 | 오류율이 기준값 이하 | 되돌리기 SQL | ★ |
| 3 | <서버 함수 배포> | 함수 로그 | 1시간 | 실패 0건 | 이전 커밋 재배포 | ★ |
| 4 | <고객 이미지 v{v}> | 미러 manifest와 layer 전부 200, selftest 0 failing | 고객 첫 업데이트 | /version = {v} | active_version 복귀 | ★ 태그, ★ 전환 |

## 롤백 준비

| 바뀌는 것 | 미리 잡아 둔 것(이전 버전, ID, SQL) | 확인 |
|---|---|---|
| | | [ ] |

## 마무리

- [ ] 관찰 결과를 로그에 적음
- [ ] 고객용 노트(확인된 효과만, 코드와 내부 동작과 고객 정보 없이)
- [ ] 내부 changelog
- [ ] 개선점을 이슈로 남김: #<n>
- [ ] 프로젝트 메모리 갱신
