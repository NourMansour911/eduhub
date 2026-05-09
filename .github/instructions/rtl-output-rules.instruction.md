
# RTL Safe Output Rules (Arabic Dialect - Strict)

## Purpose
Ensure clean Arabic rendering using simple dialect (not formal Arabic), with strict separation of any English or technical content.

## When To Apply
**ALWAYS apply these rules in every response containing Arabic text**, regardless of context. This is a non-negotiable requirement.

---

## STRICT RULES (MANDATORY)

- NEVER mix Arabic and English in the same line.
- ANY English word, term, symbol, or technical phrase MUST be on a separate line.
- EVEN a single English word requires a new line.
- Code, variables, function names, APIs, and identifiers MUST always be on their own line.
- NEVER embed English inside Arabic sentences under any condition.
- ALWAYS use simple Arabic dialect (e.g. Egyptian), NOT formal Arabic.
- AVOID complex grammar or academic wording.
- KEEP sentences short, clear, and direct.
- DO NOT use heavy formal expressions or classical Arabic structures.

---

## TECHNICAL TERM HANDLING

When explaining a technical term:

1. Write explanation in Arabic (dialect)
2. Write the English term on a separate line
3. Continue explanation in Arabic

---

## FORMATTING RULES

- Add spacing between Arabic and English blocks when needed for clarity.
- Do NOT repeat English terms excessively.
- Maintain consistent tone throughout the response.
- Lists must follow the same separation rule:
  - Arabic lines only
  - English lines only

---

## CORRECT EXAMPLE ✅

ده شرح بسيط للفكرة

Gradient Descent

بيستخدم علشان يقلل الخطأ تدريجي

---

## INCORRECT EXAMPLE ❌

ده شرح Gradient Descent للفكرة

---

## For Copilot / AI Systems

### Apply Rule In Every Response

1. **Before writing**: Check if response contains any Arabic text.
2. **If Arabic present**: Apply separation rule IMMEDIATELY.
3. **No exceptions**: Even single English word → new line.
4. **Every term**: Function names, error codes, file paths → new line.
5. **Every time**: This is not optional for any response.

### Checklist
- [ ] No English word mixed with Arabic on same line?
- [ ] All code/technical terms isolated on own lines?
- [ ] Using simple dialect (Egyptian), not formal?
- [ ] Short sentences, clear phrasing?
- [ ] Spacing between Arabic and English blocks?

### Load Rules
This file is stored in:
```
.github/instructions/rtl-output-rules.instruction.md
```

Referenced in user memory at:
```
/memories/rtl-arabic-rules.md
```

**Load and apply both automatically in every Arabic response.**