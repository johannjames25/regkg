"""Score detected needs against the planted gaps."""
import json


def _text(k):
    return " ".join([k.description] + k.evidence).lower()


def evaluate(needs, gt_path):
    gaps = json.load(open(gt_path, encoding="utf-8"))["gaps"]
    found, used = {}, set()
    for g in gaps:
        req = g["req"]
        for k in needs:
            same = k.req == req
            if same and (any(t.lower() in _text(k) for t in g["terms"]) or (req.startswith("§") and k.knowledge_type == "COVERAGE")):
                found[g["id"]] = k.id
                used.add(k.id)
                break
    tp = len(found)
    by_nature = {}
    for g in gaps:
        s = by_nature.setdefault(g["nature"], [0, 0])
        s[1] += 1
        s[0] += g["id"] in found
    precision = len(used) / len(needs) if needs else 0.0
    return {"recall": tp / len(gaps), "found": tp, "total": len(gaps), "precision": precision,
            "needs": len(needs), "unmatched_needs": [k.id for k in needs if k.id not in used],
            "missed": [g["id"] for g in gaps if g["id"] not in found], "by_nature": by_nature, "map": found}
