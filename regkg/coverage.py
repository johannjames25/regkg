"""Lexical alignment between regulation clauses and BRD requirements (no LLM).

TF-IDF cosine over lightly stemmed tokens, after expanding BRD glossary abbreviations
("GL" -> "General Ledger") so the two vocabularies meet. This proposes 'implements' links
and flags regulatory obligations that no requirement seems to implement.
"""
import math, re
from collections import Counter

STOP = set("the a an of to and or in on for by with from as at be is are shall may all any its their "
           "this that each per which whose other others one two into under than".split())


def _stem(w):
    for suf in ("ations", "ation", "ings", "ing", "ies", "ied", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def _tokens(text):
    return [_stem(w) for w in re.findall(r"[a-z]+", text.lower()) if w not in STOP and len(w) > 2]


def expand_glossary(text, glossary):
    for term, definition in glossary.items():
        key = term.split()[0]
        head = definition.split(",")[0]
        text = re.sub(rf"\b{re.escape(key)}\b", f"{key} ({head})", text)
    return text


def align(clauses, requirements, glossary, link_threshold=0.18):
    docs = {c.id: _tokens(c.text) for c in clauses}
    docs.update({r.id: _tokens(r.title + " " + expand_glossary(r.text, glossary)) for r in requirements})
    df = Counter(t for toks in docs.values() for t in set(toks))
    n = len(docs)
    vec = {}
    for k, toks in docs.items():
        tf = Counter(toks)
        v = {t: (1 + math.log(c)) * math.log(n / df[t]) for t, c in tf.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vec[k] = {t: x / norm for t, x in v.items()}

    def cos(a, b):
        return sum(x * vec[b].get(t, 0.0) for t, x in vec[a].items())

    links = []
    for c in clauses:
        for r in requirements:
            s = cos(c.id, r.id)
            if s >= link_threshold:
                links.append((r.id, c.id, round(s, 3)))
    covered = {c for _, c, _ in links}
    uncovered = [c.id for c in clauses if c.kind in ("obligation", "exemption") and c.id not in covered]
    return links, uncovered
