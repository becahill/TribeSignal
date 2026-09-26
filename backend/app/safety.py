"""Conservative English emergency phrases, not a general risk classifier.

This gate only stops analysis; it neither assigns severity nor calculates priority.
Keep additions explicit and covered by positive and ordinary-report examples.
"""

import re


EMERGENCY_MESSAGE = (
    "This report may describe an active emergency. TribeSignal is for infrastructure "
    "triage, not emergency response. Contact emergency services or the appropriate "
    "campus emergency channel before using normal infrastructure triage."
)

_RULES = tuple(re.compile(pattern) for pattern in (
    r"\b(?:active|ongoing) (?:electrical )?fire\b"
    r"(?! (?:alarm|panel|drill|door|extinguisher|exit|damage))",
    r"\b(?:is|are|it's|they're) (?:currently )?on fire\b",
    r"\b(?:there is|there's|we have) (?:an? )?(?:electrical )?fire\b"
    r"(?! (?:alarm|panel|drill|door|extinguisher|exit|damage))",
    r"\b(?:gas leak|gas is leaking)\b(?! (?:detector|sensor|drill|test))",
    r"\b(?:there is|there's|there was|we heard) an? explosion\b",
    r"\ban? explosion (?:has |just )?(?:happened|occurred)\b",
    r"\b(?:someone|somebody|a person|people|a student|students|my friend|"
    r"i am|i'm|we are|we're) (?:is |are )?(?:still )?(?:trapped|stuck) "
    r"(?:inside|in) (?:an? |the )?(?:elevator|lift)\b",
    r"\b(?:someone|somebody|a person|a student|my friend) "
    r"(?:is |has been )?(?:seriously|severely|critically) injured\b",
    r"\bimmediate threat to (?:someone's |human )?life\b",
    r"\bsmoke\b.{0,80}\b(?:cannot breathe|can't breathe|trapped|choking)\b",
    r"\b(?:cannot breathe|can't breathe|trapped|choking)\b.{0,80}\bsmoke\b",
    r"\b(?:flooding|floodwater|water)\b.{0,80}"
    r"\b(?:reaching|touching|around|contact with) (?:the )?"
    r"(?:live|energized|sparking) (?:wires|outlets|electrical equipment|electrical panel)\b",
))
_CLAUSE_BREAK = re.compile(r"[.!?;\n]|\b(?:but|however|yet)\b")
_NON_CURRENT = re.compile(
    r"\b(?:drill|training|hypothetical|yesterday|last (?:night|week|month|year))\b"
)
_NEGATED_OR_CONDITIONAL = re.compile(
    r"\b(?:no|not|never|without|isn't|aren't|wasn't|weren't|if|in case of)\b"
)
_RESOLVED = re.compile(
    r"^ (?:is|was|has been) (?:repaired|fixed|resolved|extinguished|over|out)\b"
)


def is_emergency(text: str) -> bool:
    normalized = text.lower().replace("’", "'")
    for raw_clause in _CLAUSE_BREAK.split(normalized):
        clause = " ".join(raw_clause.split())
        if _NON_CURRENT.search(clause):
            continue
        for rule in _RULES:
            for match in rule.finditer(clause):
                # Local context avoids treating an explicit denial as an emergency.
                prefix = clause[max(0, match.start() - 45):match.start()]
                if (
                    not _NEGATED_OR_CONDITIONAL.search(prefix)
                    and not _RESOLVED.search(clause[match.end():])
                ):
                    return True
    return False
