# 501 새 판 내기

키트를 고쳤으면 아래 순서대로 새 판을 냅니다. 모두 비공개 강의 저장소(mmk-skool-classroom)의 로컬 세션에서 해요.

1. 강의 저장소에서 `courses/2026-11-15-manju-workshop/kits/<kit>` 을 고치고 PR 로 머지합니다.
2. 검사합니다. 강의 사이트 호스트 목록은 환경 변수로만 넘기고, git 이나 출력에는 남기지 않습니다.
   ```sh
   KITS_BLOCK_EXTRA="<호스트 정규식, 한 줄에 하나>" python3 scripts/publish-kits.py check
   ```
3. 이 저장소에 PR 을 엽니다(`--kits setup-check,cleanup` 으로 일부만 낼 수도 있어요).
   ```sh
   KITS_BLOCK_EXTRA="…" python3 scripts/publish-kits.py pr
   ```
4. 이 저장소에서 그 PR 을 머지합니다. 머지는 메인 세션이 합니다.
5. 새 판을 냅니다. 숫자는 지난 판보다 하나 큰 것으로 씁니다.
   ```sh
   KITS_BLOCK_EXTRA="…" python3 scripts/publish-kits.py release seoul-3-vN
   ```
6. 로그인 없이 확인합니다(docs/agents/VERIFY.md 3단계).
   - `latest` 주소 두 개가 200 인지
   - 받은 zip 의 `VERSION` 이 새 판인지
   - API 의 `tag_name` 이 새 판인지

## 되돌리기

잘못 낸 판은 지우지 않습니다. 고친 내용으로 다음 판을 하나 더 냅니다. 이미 그 판을 받은 수강생의 키트가 「예전 판」으로 알아보고 새로 받습니다.

## 하면 안 되는 것

- 태그 지우기, 이름 바꾸기, 같은 이름으로 다시 내기
- 이 저장소에서 키트 파일을 손으로 고치기
- 강의 사이트 주소나 내부 이름을 이 저장소에 적기
