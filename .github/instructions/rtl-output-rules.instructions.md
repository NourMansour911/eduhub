---
description: "Use when answering in Arabic, explaining technical topics to Arabic-speaking users, or generating bilingual-safe output formatting. Enforces strict line separation between Arabic and English terms."
name: "RTL Safe Output Rules (Arabic)"
---

# RTL Safe Output Rules (Arabic)

This project uses Arabic explanations, but Copilot MUST ensure clean rendering.

## STRICT RULES

- NEVER mix Arabic and English in the same line.
- If an English word, symbol, or technical term is required, it MUST be placed on a separate line.
- Any English content (including variable names, code, or technical terms) must always appear in its own line alone.
- Do NOT embed English words inside Arabic sentences under any circumstance.
- Even a single English word inside Arabic text requires splitting into a new line.
- Maintain strict line separation between Arabic explanation lines and English/technical lines.

## EXAMPLE (Correct)

هذا شرح للمعادلة

Cost Function

تستخدم في تنظيم النموذج

## EXAMPLE (Incorrect)

هذا شرح Cost Function للمعادلة ❌