"""Build a single-file interactive demo (outputs/demo.html) from a pipeline run.

The page needs no server and no install: open it in a browser. Pick a requirement on the left
to see its text with every concrete detail highlighted by where it came from, its
regulation-only twin, and the gaps found, each with a likely source and a question for an SME.
"""
import json

TEMPLATE_PATH = __file__.replace("demo.py", "demo_template.html")


def _segments(text, anchors):
    """Split requirement text into segments tagged with highlight class and decision underline."""
    n = len(text)
    mark = [""] * n
    under = [False] * n
    tip = [""] * n
    for a in anchors:
        start = 0
        while True:
            i = text.find(a.text, start)
            if i < 0:
                break
            for k in range(i, i + len(a.text)):
                if a.kind == "DECISION":
                    under[k] = True
                elif not mark[k]:
                    mark[k] = {"REG": "reg", "BRD": "brd"}.get(a.grounding, "none")
                    ref = a.grounded_ref
                    if ref.startswith("glossary"):
                        src = "defined in the BRD glossary"
                    elif ref.startswith("§"):
                        src = f"found in regulation {ref}"
                    else:
                        src = "no source found"
                    tip[k] = f"{a.kind.replace('_', ' ').lower()}: {src}"
            start = i + len(a.text)
    segs, cur = [], None
    for k, ch in enumerate(text):
        key = (mark[k], under[k], tip[k])
        if cur and cur["key"] == key:
            cur["t"] += ch
        else:
            cur = {"key": key, "t": ch}
            segs.append(cur)
    return [{"t": s["t"], "m": s["key"][0], "u": s["key"][1], "tip": s["key"][2]} for s in segs]


def build_demo(path, clauses, brd, anchors, needs, semantic, profile, ev_det, ev_full):
    sem = (semantic or {}).get("requirements", {})
    cov = (semantic or {}).get("coverage", {})
    reqs = []
    for r, p in zip(brd.requirements, profile):
        s = sem.get(r.id, {})
        reqs.append({
            "id": r.id, "title": r.title, "text": r.text, "level": p["level"],
            "segs": _segments(r.text, anchors[r.id]),
            "twin": s.get("twin", ""),
            "links": s.get("alignment", []),
            "gaps": [{"id": k.id, "type": k.knowledge_type.replace("_", " ").lower(), "level": k.level,
                      "what": k.description, "evidence": k.evidence, "source": k.sources[0] if k.sources else "",
                      "others": k.sources[1:], "q": k.sme_question, "conflict": k.conflict,
                      "by": "+".join(k.origin)} for k in needs if k.req == r.id],
        })
    cls = []
    for c in clauses:
        info = cov.get(c.id, {})
        cls.append({"id": c.id, "section": c.section, "kind": c.kind, "text": c.text,
                    "status": info.get("status", ""), "by": info.get("by", []), "note": info.get("note", ""),
                    "gaps": [{"id": k.id, "what": k.description} for k in needs if k.req == c.id]})
    data = {"reqs": reqs, "clauses": cls,
            "eval": {"det": ev_det, "full": ev_full},
            "counts": {l: sum(p["level"] == l for p in profile) for l in ("P0", "P1", "P2", "P3")},
            "nNeeds": len(needs)}
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        page = f.read()
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    with open(path, "w", encoding="utf-8") as f:
        f.write(page.replace("/*__DATA__*/null", blob))
