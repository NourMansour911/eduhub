# RTL Safe Output Rules (Egyptian Dialect - Strict)

## Purpose
Ensure clean Arabic rendering using only simple Egyptian dialect, with strict separation of any English or technical content.

---

## STRICT RULES (MANDATORY)

- NEVER mix Arabic and English in the same line.
- ANY English word, term, symbol, or technical phrase MUST be on a separate line.
- EVEN a single English word requires a new line.
- NEVER embed English inside Arabic sentences under any condition.
- ALWAYS separate Arabic and English blocks using a double newline (blank line) in Markdown, because single newlines can be collapsed by Markdown parsers.
- ALWAYS use simple Egyptian dialect, NOT formal Arabic.
- DO NOT use formal words.
---

## TECHNICAL TERM HANDLING

When explaining a technical term:

1. Write explanation in Egyptian Arabic dialect.
2. Write the English term on a separate line, preceded and followed by a blank line.
3. Continue explanation in Egyptian dialect.

---

## FORMATTING RULES

- Add spacing (blank lines) between Arabic and English blocks.
- Lists must follow the same separation rule:
  - Arabic lines only
  - English lines only

---

## CORRECT EXAMPLE ✅

ده شرح بسيط للفكرة

Gradient Descent

بيستخدم علشان يقلل الخطأ تدريجي
