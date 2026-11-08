# Korean writing (docs, UI copy, PR text, reports)

The owner reads Korean. Read this before writing any Korean a person will see. Managed by mmk-crew: copied on every `setup` run.

## Words
- No stiff Sino-Korean calques of English terms. If the natural Korean is awkward, write the English term in Hangul as said aloud: provider → 프로바이더 (not 공급자), deploy → 배포 (common, fine). Keep code identifiers in English.
- One term per concept. The project glossary is docs/agents/GLOSSARY.md (project-owned, setup never overwrites it): check it before writing, and add a row in the same PR whenever you pick or change a term.
- Plain words over jargon in owner-facing text; explain infra as what it is, why, and the risk.

## Sentences
- No can-translationese: 「~할 수 있어요/있습니다」 → 「됩니다」, 「가능한」, or just the verb. Grep `수 있` to 0 in user-facing copy.
- No em/en dash (—, –) or middle dot (·). Use commas, 「과/와」, or a new sentence.
- First person singular: 저, 제 (never 저희, 우리) in public text.
- Tone: facts and official info in 합쇼체 (~합니다), action prompts in 해요체 (~해 주세요). Not all 해요체.
- No nominalised stacks (「~의 진행의 완료」), no reflexive three-item lists, no "AI tells".
- Korean line breaks: `word-break: keep-all` in UI; never split a modifier from its noun.

## Customer mail and notices (business tone)
Automated mail (thank-you, receipts, opt-out notes) reads like a company letter, not a chat.
- No colloquial service verbs: 「빼 드리겠습니다」 → 「발송을 중단하겠습니다」, 「알려 드릴게요」 → 「안내해 드리겠습니다」.
- No purpose + passive calque: 「~하기 위해 발송되었습니다」 → 「~분께 보내 드리는 … 메일입니다」.
- A reason clause needs its main clause: 「동의해 주셔서 (감사합니다 없이) 보내 드리겠습니다」 → 「동의해 주신 연락처로 보내 드리겠습니다」.
- Requests to the reader take 「~해 주시거나」, 「~해 주세요」, not bare 「~하시거나」.
- Do not repeat the same verb (안내, 반영) in neighbouring paragraphs.
- Never put what a visitor typed (name, free text) into a mail sent to an address they typed: an open relay for spam. Use fixed copy and the round's label only.
- Example, a review thank-you: 「{label}에 참석해 주시고 후기까지 남겨 주셔서 감사합니다. 보내 주신 후기는 꼼꼼히 읽고 다음 강의 준비에 반영하겠습니다.」

## Before shipping
- Run Korean copy through the `korean-copy-reviewer` agent (docs, UI strings, PR body, release notes).
- Checks: `grep -nE '수 있|—|–|·'` on changed Korean files returns nothing that ships.
- When handing Korean work to another session, include: "용어는 어색한 직역 대신 영어 음역, 번역투 검수".
