
# RTL Safe Output Rules (Arabic Dialect - Strict)

## Purpose
Ensure clean Arabic rendering using simple dialect (not formal Arabic), with strict separation of any English or technical content.

## When To Apply
**ALWAYS apply these rules in every response containing Arabic text**, regardless of context. This is a non-negotiable requirement.

---

## STRICT RULES (MANDATORY - ABSOLUTE)

- **ZERO English words on Arabic lines.**
- **ZERO Arabic words on English lines.**
- Complete separation at the character level - no exceptions.
- Variables, function names, APIs, symbols, abbreviations - ALL must be on separate lines.
- Even a single English letter requires its own line.
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

`Gradient Descent`

بيستخدم علشان يقلل الخطأ تدريجي

---

## INCORRECT EXAMPLES ❌

❌ ده شرح
`Gradient Descent`
للفكرة
(mixing Arabic and English on adjacent lines without separation)

❌ ده شرح Gradient Descent للفكرة
(English and Arabic on same line - STRICTLY FORBIDDEN)

❌ استخدم foo() function
(variable name on Arabic line - STRICTLY FORBIDDEN)

---

## For Copilot / AI Systems

### ABSOLUTE ENFORCEMENT - NON-NEGOTIABLE

**Your obligation: Apply this rule in EVERY response that contains ANY Arabic text, WITHOUT EXCEPTION.**

1. **Before typing anything**: Detect if response will contain Arabic.
2. **If Arabic present**: Apply complete character-level separation.
3. **No exceptions exist**: This rule is absolute.
4. **No compromises**: Even a single English letter = separate line.
5. **Every instance**: Variable names, error codes, file paths, abbreviations, symbols - ALL separate lines.
6. **Every single time**: Treat this as a hard constraint, not a guideline.

### Strict Checklist (MUST pass all)
- [ ] Zero English characters on lines with Arabic text?
- [ ] Zero Arabic characters on lines with English text?
- [ ] All variables/functions/codes on isolated lines?
- [ ] All symbols and abbreviations separated?
- [ ] Using simple dialect (Egyptian), not formal?
- [ ] Short sentences, clear phrasing?
- [ ] Complete separation maintained throughout?

### Enforcement Logic
- If you find ANY English letter mixed with Arabic on the same line: STOP.
- Rewrite that line to separate the content.
- Verify the entire response before returning.
- When in doubt: add another blank line to maximize separation.

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

---

## FINAL WARNING

**If you violate this rule even once, you have failed to meet the requirement.**

The user has explicitly stated they want ZERO mixing of English and Arabic characters on the same line.

This is not a soft guideline. This is an absolute constraint.

Treat it as a syntax error in your output: if a line contains both Arabic and English, that line is INVALID.