"""Knowledge anchors: the concrete 'specifics' in a BRD requirement.

Idea: a regulation is written at the level of concepts ("exposure", "connected counterparties").
A BRD has to become concrete: table names, field names, systems, codes, numbers, documents,
and decisions ("where X is null, do Y"; "not in this release"). Every concrete specific that
cannot be traced back to the regulation or to something the BRD itself defines is a point where
outside knowledge entered. This layer is deterministic, cheap and needs no LLM.
"""
import re
from dataclasses import dataclass

DOC_REF = re.compile(
    r"\b(?:[A-Z][A-Za-z]*\s+){0,3}(?:Policy|Manual|Guideline|Procedure|Circular|Standard)\s+v?\d+(?:\.\d+)*"
    r"(?:,?\s+Annexure\s+\w+)?|\bAnnexure\s+\w+|\b[A-Z]{2,}-\d+\b")
DATA_FIELD = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")
UNIT = re.compile(r"\b(?:INR|USD|EUR|GBP)\s+(?:lakhs?|crores?|millions?|thousands?)\b"
                  r"|\b(?:one|two|three|four|\d+)\s+decimals?\b", re.I)
PARAMETER = re.compile(r"\bT\+\d+(?:\s+(?:business|calendar)\s+days)?"
                       r"|\b\d+(?:\.\d+)?(?:\s*-\s*\d+)?(?:\s*(?:percent|%|business days|calendar days|days))?")
ACRONYM = re.compile(r"\b[A-Z]{2,}\b")
CAPWORD = re.compile(r"\b[A-Z][a-z]{2,}\b")
FALLBACK = re.compile(r"[^.]*\b(?:where|if|when)\b[^.]*\b(?:is|are)\s+(?:null|missing|blank|not available)\b[^.]*\.", re.I)
SCOPE_LIMIT = re.compile(r"[^.]*(?:\bnot\s+(?:considered|included|covered|in scope)\b|\bin this release\b|\bout of scope\b)[^.]*\.", re.I)
RATIONALE = re.compile(r"\b(?:because|as per|in line with|since|due to|rationale|so that)\b", re.I)
STOP_ACRONYMS = {"BRD", "LE"}


@dataclass
class Anchor:
    text: str
    kind: str                 # DOC_REF | DATA_FIELD | UNIT | PARAMETER | ACRONYM | SYSTEM | DECISION
    req: str
    grounding: str = "NONE"   # REG | BRD | NONE
    grounded_ref: str = ""    # clause id or glossary term
    subkind: str = ""         # FALLBACK / SCOPE_LIMIT for decisions
    context_system: str = ""  # system named in the same requirement (CBS, TF, ...)


def _mask(text, spans):
    chars = list(text)
    for s, e in spans:
        for i in range(s, e):
            chars[i] = " "
    return "".join(chars)


def _numbers(s):
    return set(re.findall(r"\d+(?:\.\d+)?", s))


def _initials_in(acr, reg_text):
    words = re.findall(r"[a-z]+", reg_text.lower())
    n = len(acr)
    for i in range(len(words) - n + 1):
        if "".join(w[0] for w in words[i:i + n]) == acr.lower():
            return " ".join(words[i:i + n])
    return None


def _clause_containing(phrase, clauses):
    for c in clauses:
        if phrase.lower() in c.text.lower():
            return c.id
    return ""


def extract_anchors(req, clauses, glossary):
    reg_text = " ".join(c.text for c in clauses)
    reg_lower, reg_nums = reg_text.lower(), _numbers(reg_text)
    gl_keys = {k.split()[0].upper(): k for k in glossary}
    systems_here = [k for k in gl_keys if re.search(rf"\b{k}\b", req.text) and "system" in glossary[gl_keys[k]].lower()]
    ctx_sys = systems_here[0] if systems_here else ""
    text, anchors, spans = req.text, [], []

    def add(m, kind):
        spans.append(m.span())
        anchors.append(Anchor(m.group(0).strip(" ,"), kind, req.id, context_system=ctx_sys))

    for m in DOC_REF.finditer(text): add(m, "DOC_REF")
    text2 = _mask(text, spans)
    for m in DATA_FIELD.finditer(text2): add(m, "DATA_FIELD")
    text2 = _mask(text, spans)
    for m in UNIT.finditer(text2): add(m, "UNIT")
    text2 = _mask(text, spans)
    for m in PARAMETER.finditer(text2):
        if m.group(0).strip(): add(m, "PARAMETER")
    text2 = _mask(text, spans)
    for m in ACRONYM.finditer(text2):
        if m.group(0) not in STOP_ACRONYMS: add(m, "ACRONYM")
    text2 = _mask(text, spans)
    for m in CAPWORD.finditer(text2):   # capitalised mid-sentence words unknown to both documents
        before = text2[:m.start()].rstrip()
        sentence_start = before == "" or before.endswith(".")
        w = m.group(0).lower()
        known = w in reg_lower or any(w in (k + " " + v).lower() for k, v in glossary.items())
        if not sentence_start and not known:
            add(m, "SYSTEM")
    for rx, sub in ((FALLBACK, "FALLBACK"), (SCOPE_LIMIT, "SCOPE_LIMIT")):
        for m in rx.finditer(req.text):
            a = Anchor(m.group(0).strip(), "DECISION", req.id, subkind=sub, context_system=ctx_sys)
            anchors.append(a)

    sys_anchor = next((a.text for a in anchors if a.kind == "SYSTEM"), "")
    if not ctx_sys and sys_anchor:
        for a in anchors:
            if a.kind != "SYSTEM":
                a.context_system = sys_anchor

    # --- grounding --------------------------------------------------------
    for a in anchors:
        t = a.text
        if a.kind == "PARAMETER":
            if _numbers(t) and _numbers(t) <= reg_nums:
                a.grounding, a.grounded_ref = "REG", _clause_containing(sorted(_numbers(t))[0], clauses)
        elif a.kind in ("DOC_REF", "UNIT"):
            if t.lower() in reg_lower:
                a.grounding, a.grounded_ref = "REG", _clause_containing(t, clauses)
            elif t.split("-")[0].upper() in gl_keys and a.kind == "DOC_REF" and t in " ".join(glossary):
                a.grounding, a.grounded_ref = "BRD", "glossary"
        elif a.kind == "ACRONYM":
            if t in gl_keys:
                a.grounding, a.grounded_ref = "BRD", f"glossary:{gl_keys[t]}"
            elif re.search(rf"\b{t.lower()}\b", reg_lower):
                a.grounding, a.grounded_ref = "REG", _clause_containing(t, clauses)
            else:
                phrase = _initials_in(t, reg_text)
                if phrase:
                    a.grounding, a.grounded_ref = "REG", _clause_containing(phrase, clauses)
        elif a.kind == "DATA_FIELD":
            if t in glossary:
                a.grounding, a.grounded_ref = "BRD", f"glossary:{t}"
        elif a.kind == "DECISION":
            if RATIONALE.search(req.text):
                a.grounding, a.grounded_ref = "BRD", "rationale stated in requirement"
    seen, unique = set(), []
    for a in anchors:
        if (a.kind, a.text) not in seen:
            seen.add((a.kind, a.text)); unique.append(a)
    return unique
