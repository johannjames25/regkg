"""Semantic layer: what the anchors can't see.

Three LLM tasks per requirement, in one call:
  1. Alignment   - which clauses does it implement, and how (entailed / refines / extends / contradicts)
  2. Regulation-only twin - rewrite the requirement using ONLY the regulation. The diff between
     the twin and the real requirement is exactly the knowledge the business team added.
  3. Premise elicitation - the facts/decisions needed to get from the clauses to the requirement,
     each typed and marked as stated in REG, BRD, or NONE.
Plus one coverage call over all clauses.

Modes: 'cache' (default, reads data/llm_cache.json) or 'anthropic' (live, needs ANTHROPIC_API_KEY).
"""
import json, os, re, urllib.request

KNOWLEDGE_TYPES = ["DATA_LINEAGE", "REFERENCE_DATA", "SYSTEM_CAPABILITY", "CALCULATION_METHOD",
                   "REGULATORY_INTERPRETATION", "SCOPING_DECISION", "OPERATIONAL_PRACTICE",
                   "REFERENCED_DOCUMENT", "PARAMETER"]

REQ_PROMPT = """You are analysing how a Business Requirements Document (BRD) was derived from a regulation.

REGULATION (clause id: text):
{regulation}

BRD GLOSSARY:
{glossary}

BRD REQUIREMENT {req_id}: {req_text}

Do three things.
1. ALIGNMENT: list the regulation clauses this requirement implements. For each, give a relation:
   "entailed" (follows directly), "refines" (makes a regulatory concept more specific),
   "extends" (adds something the regulation does not mention), or "contradicts" (conflicts in any detail).
2. TWIN: rewrite the requirement as a careful analyst would write it using ONLY the regulation,
   with no knowledge of this bank's systems, products or past decisions.
3. PREMISES: list every fact or decision needed to get from the clauses to the ACTUAL requirement
   that is not in the twin. Be specific (name the field, number, or decision), never generic.
   For each premise give knowledge_type from {types}, stated_in = "REG" | "BRD" | "NONE"
   (BRD means stated in the glossary or requirement text itself, including a stated rationale),
   and an sme_question a business analyst could ask to resolve it (empty if stated_in is not NONE).

Return ONLY JSON: {{"alignment":[{{"clause":"...","relation":"..."}}],"twin":"...",
"premises":[{{"premise":"...","knowledge_type":"...","stated_in":"...","sme_question":"..."}}]}}"""

COVERAGE_PROMPT = """REGULATION (clause id: text):
{regulation}

BRD REQUIREMENTS:
{requirements}

For each regulation clause that creates an obligation, definition used in reporting, or exemption,
say whether the BRD covers it: "full", "partial" or "none", which requirements cover it, and a short
note on what is missing for partial/none.
Return ONLY JSON: {{"<clause id>": {{"status":"...","by":["BR-.."],"note":"..."}}}}"""


def _call_anthropic(prompt, model):
    body = json.dumps({"model": model, "max_tokens": 2000,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "content-type": "application/json", "x-api-key": os.environ["ANTHROPIC_API_KEY"],
        "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.load(r)
    text = "".join(b.get("text", "") for b in data["content"])
    text = re.sub(r"```(?:json)?|```", "", text).strip()
    return json.loads(text)


def run_semantic(clauses, brd, mode="cache", cache_path="data/llm_cache.json",
                 model=os.environ.get("REGKG_MODEL", "claude-sonnet-5-5")):
    if mode == "cache":
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)
    reg = "\n".join(f"{c.id}: {c.text}" for c in clauses)
    gl = "\n".join(f"{k}: {v}" for k, v in brd.glossary.items())
    out = {"_provenance": f"live run, model={model}", "requirements": {}}
    for r in brd.requirements:
        prompt = REQ_PROMPT.format(regulation=reg, glossary=gl, req_id=r.id, req_text=r.text,
                                   types=", ".join(KNOWLEDGE_TYPES))
        out["requirements"][r.id] = _call_anthropic(prompt, model)
    reqs = "\n".join(f"{r.id}: {r.text}" for r in brd.requirements)
    out["coverage"] = _call_anthropic(COVERAGE_PROMPT.format(regulation=reg, requirements=reqs), model)
    with open(cache_path.replace(".json", "_live.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    return out
