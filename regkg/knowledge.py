"""Turn anchors, semantic premises and coverage into KnowledgeNeed nodes.

Knowledge provenance levels (borrowing the idea of the DTCF validation hierarchy:
say explicitly how far each piece of the BRD can be checked):
  P0  regulation-entailed        - traceable to a clause
  P1  explicit business knowledge - not in the regulation, but defined or justified in the BRD
  P2  referenced but absent       - names an artifact (table, system, document, code list) we don't have
  P3  tacit                       - a number, convention or decision with no reference and no rationale
P2 gaps are cheap to close (go fetch the artifact). P3 gaps need a person or a decision record.
"""
from dataclasses import dataclass, field

SOURCE_MAP = {
    "DATA_LINEAGE": ["{sys}data dictionary (or enterprise metadata catalog)", "Source system interface specs", "Data lineage tool"],
    "REFERENCE_DATA": ["Reference data / code list master", "{sys}customer or product master documentation", "Data governance (data owner)"],
    "SYSTEM_CAPABILITY": ["Application inventory / architecture documents", "System user manuals", "IT change log"],
    "CALCULATION_METHOD": ["Risk methodology documents", "Credit risk policy", "Existing report logic (previous BRDs, code)"],
    "REGULATORY_INTERPRETATION": ["Compliance interpretation memos", "Regulator FAQs / Q&A", "Decision log / steering minutes"],
    "SCOPING_DECISION": ["Change requests / JIRA", "Release scope decisions / steering minutes", "Project RAID log"],
    "OPERATIONAL_PRACTICE": ["Regulatory calendar / submission SOP", "Prior submissions", "Regulator template specification"],
    "REFERENCED_DOCUMENT": ["Policy repository / document management system"],
    "PARAMETER": ["Reconciliation or control policy", "Finance chart of accounts", "Decision log"],
    "COVERAGE": ["Compliance obligations register", "Data governance / BCBS 239 programme", "BA / compliance review"],
}
P2_TYPES = {"DATA_LINEAGE", "REFERENCE_DATA", "SYSTEM_CAPABILITY", "REFERENCED_DOCUMENT"}
LEVEL_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


@dataclass
class KnowledgeNeed:
    id: str
    req: str
    knowledge_type: str
    level: str
    description: str
    evidence: list = field(default_factory=list)
    origin: list = field(default_factory=list)       # "anchor" | "semantic" | "coverage"
    sources: list = field(default_factory=list)
    sme_question: str = ""
    conflict: bool = False
    system: str = ""


def _anchor_type(a, req_anchors):
    if a.kind == "DATA_FIELD":
        return "REFERENCE_DATA" if a.text.endswith(("_ID", "_CODE")) else "DATA_LINEAGE"
    if a.kind == "DOC_REF":
        return "REFERENCED_DOCUMENT"
    if a.kind == "SYSTEM":
        return "SYSTEM_CAPABILITY"
    if a.kind == "UNIT":
        return "OPERATIONAL_PRACTICE"
    if a.kind == "DECISION":
        return "REGULATORY_INTERPRETATION" if a.subkind == "FALLBACK" else "SCOPING_DECISION"
    if a.kind == "PARAMETER":
        if any(x.kind == "DATA_FIELD" and x.text.endswith("_CODE") for x in req_anchors):
            return "REFERENCE_DATA"
        if "day" in a.text:
            return "OPERATIONAL_PRACTICE"
        return "PARAMETER"
    return "DATA_LINEAGE"


def _question(kt, evidence, system):
    ev = ", ".join(evidence)
    where = f" in {system}" if system else ""
    return {
        "DATA_LINEAGE": f"Where are {ev} documented{where}, and how do they map to the regulatory concept?",
        "REFERENCE_DATA": f"Who maintains {ev}, and what are the valid values and their meaning?",
        "SYSTEM_CAPABILITY": f"What is {ev}, and is it the system of record for this data?",
        "REFERENCED_DOCUMENT": f"Can we get {ev}, and which version is authoritative?",
        "OPERATIONAL_PRACTICE": f"Where does '{ev}' come from: the regulator's template, or internal practice?",
        "PARAMETER": f"Who set {ev}, and where is the approval recorded?",
        "REGULATORY_INTERPRETATION": f"What is the basis for this rule, and was it approved by compliance? ('{ev[:90]}')",
        "SCOPING_DECISION": f"Why was this scoped out, and is there a plan to cover it? ('{ev[:90]}')",
    }.get(kt, f"What knowledge supports '{ev}'?")


def build_needs(requirements, anchors_by_req, semantic, uncovered_lexical, clauses):
    needs, n = [], 0

    def new(**kw):
        nonlocal n
        n += 1
        k = KnowledgeNeed(id=f"KN-{n:02d}", **kw)
        needs.append(k)
        return k

    for r in requirements:
        anchors = anchors_by_req[r.id]
        groups = {}
        for a in anchors:
            if a.grounding != "NONE":
                continue
            kt = _anchor_type(a, anchors)
            groups.setdefault(kt, []).append(a)
        for kt, grp in groups.items():
            level = "P2" if kt in P2_TYPES else "P3"
            sys = next((a.context_system for a in grp if a.context_system), "")
            if kt == "SYSTEM_CAPABILITY":
                sys = ""
            ev = [a.text for a in grp]
            new(req=r.id, knowledge_type=kt, level=level, description=f"Ungrounded {kt.lower().replace('_', ' ')}",
                evidence=ev, origin=["anchor"], system=sys,
                sources=[s.format(sys=f"{sys} " if sys else "") for s in SOURCE_MAP[kt]],
                sme_question=_question(kt, ev, sys))

    if semantic:
        for rid, s in semantic.get("requirements", {}).items():
            contradicts = any(al.get("relation") == "contradicts" for al in s.get("alignment", []))
            for p in s.get("premises", []):
                if p.get("stated_in") != "NONE":
                    continue
                kt = p.get("knowledge_type", "REGULATORY_INTERPRETATION")
                ptxt = p["premise"].lower()
                anchor_needs = [k for k in needs if k.req == rid and "anchor" in k.origin]
                match = next((k for k in anchor_needs if any(e.lower() in ptxt for e in k.evidence)), None) \
                    or next((k for k in anchor_needs if k.knowledge_type == kt and "semantic" not in k.origin), None)
                if match:   # the anchor layer already found it: enrich, don't duplicate
                    if "semantic" not in match.origin:
                        match.origin.append("semantic")
                        match.description, match.sme_question = p["premise"], p.get("sme_question") or match.sme_question
                    else:
                        match.description += " | " + p["premise"]
                        if p.get("sme_question"):
                            match.sme_question += " / " + p["sme_question"]
                else:
                    sysname = next((k.system for k in needs if k.req == rid and k.system), "")
                    new(req=rid, knowledge_type=kt, level="P2" if kt in P2_TYPES else "P3",
                        description=p["premise"], evidence=[], origin=["semantic"], system=sysname,
                        sources=[x.format(sys=f"{sysname} " if sysname else "") for x in SOURCE_MAP.get(kt, [])],
                        sme_question=p.get("sme_question", ""))
            if contradicts:
                for k in needs:
                    if k.req == rid and k.knowledge_type in ("OPERATIONAL_PRACTICE", "REGULATORY_INTERPRETATION", "PARAMETER"):
                        k.conflict = True

    # coverage gaps: regulation clauses with no (or partial) implementation
    cov_sem = (semantic or {}).get("coverage", {})
    clause_ids = {c.id: c for c in clauses}
    for cid in uncovered_lexical:
        note = cov_sem.get(cid, {}).get("note", "No requirement appears to implement this clause.")
        new(req=cid, knowledge_type="COVERAGE", level="P3", description=note,
            evidence=[clause_ids[cid].text], origin=["coverage"], sources=list(SOURCE_MAP["COVERAGE"]),
            sme_question=f"Which requirement implements {cid}, or is it handled outside this BRD?")
    for cid, info in cov_sem.items():
        if info.get("status") in ("partial", "none") and cid not in uncovered_lexical:
            new(req=cid, knowledge_type="COVERAGE", level="P3", description=info.get("note", ""),
                evidence=[clause_ids[cid].text] if cid in clause_ids else [], origin=["semantic"],
                sources=list(SOURCE_MAP["COVERAGE"]),
                sme_question=f"{cid} is only partly implemented ({info.get('note', '')}). Intentional?")
    return needs


def requirement_profile(requirements, anchors_by_req, needs, semantic):
    rows = []
    for r in requirements:
        anchors = anchors_by_req[r.id]
        mine = [k for k in needs if k.req == r.id]
        reg = sum(a.grounding == "REG" for a in anchors)
        brd = sum(a.grounding == "BRD" for a in anchors)
        level = max((k.level for k in mine), key=LEVEL_ORDER.get, default="P1" if brd else "P0")
        rel = ",".join(sorted({al["relation"] for al in (semantic or {}).get("requirements", {}).get(r.id, {}).get("alignment", [])}))
        rows.append({"req": r.id, "title": r.title, "level": level, "anchors": len(anchors),
                     "reg_grounded": reg, "brd_grounded": brd, "ungrounded": len(anchors) - reg - brd,
                     "needs": len(mine), "relations": rel,
                     "twin": (semantic or {}).get("requirements", {}).get(r.id, {}).get("twin", "")})
    return rows


def source_ranking(needs):
    """Which internal sources would close the most gaps? Tells you what to connect first."""
    score = {}
    for k in needs:
        if k.sources:
            score[k.sources[0]] = score.get(k.sources[0], 0) + 1   # primary source only
    return sorted(score.items(), key=lambda x: -x[1])
