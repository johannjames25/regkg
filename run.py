"""Regulation + BRD -> knowledge graph -> gaps -> likely sources.

Usage:
  python run.py                    # anchors + cached semantic layer (default)
  python run.py --llm none         # deterministic layer only, no LLM at all
  python run.py --llm anthropic    # live LLM calls (needs ANTHROPIC_API_KEY)
"""
import argparse, csv, json, os

from regkg.parse import parse_regulation, parse_brd
from regkg.anchors import extract_anchors
from regkg.coverage import align
from regkg.semantic import run_semantic
from regkg.knowledge import build_needs, requirement_profile, source_ranking
from regkg.graph import build_graph, export_json, draw
from regkg.evaluate import evaluate


def pipeline(reg_path, brd_path, llm):
    clauses, brd = parse_regulation(reg_path), parse_brd(brd_path)
    anchors = {r.id: extract_anchors(r, clauses, brd.glossary) for r in brd.requirements}
    links, uncovered = align(clauses, brd.requirements, brd.glossary)
    semantic = None if llm == "none" else run_semantic(clauses, brd, mode=llm)
    needs = build_needs(brd.requirements, anchors, semantic, uncovered, clauses)
    return clauses, brd, anchors, links, uncovered, semantic, needs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reg", default="data/regulation.md")
    ap.add_argument("--brd", default="data/brd.md")
    ap.add_argument("--gt", default="data/ground_truth.json")
    ap.add_argument("--llm", default="cache", choices=["none", "cache", "anthropic"])
    ap.add_argument("--out", default="outputs")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    # ablation: deterministic only vs deterministic + semantic
    det = pipeline(a.reg, a.brd, "none")
    full = pipeline(a.reg, a.brd, a.llm) if a.llm != "none" else det
    ev_det = evaluate(det[-1], a.gt) if os.path.exists(a.gt) else None
    ev_full = evaluate(full[-1], a.gt) if os.path.exists(a.gt) else None

    clauses, brd, anchors, links, uncovered, semantic, needs = full
    G = build_graph(clauses, brd, anchors, links, needs, semantic)
    export_json(G, f"{a.out}/knowledge_graph.json")
    draw(G, f"{a.out}/knowledge_graph.png")

    with open(f"{a.out}/gaps.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["need_id", "requirement_or_clause", "knowledge_type", "level", "conflict", "found_by",
                    "evidence", "what_is_missing", "primary_source", "other_sources", "sme_question"])
        for k in needs:
            w.writerow([k.id, k.req, k.knowledge_type, k.level, "yes" if k.conflict else "", "+".join(k.origin),
                        "; ".join(k.evidence), k.description, k.sources[0] if k.sources else "",
                        "; ".join(k.sources[1:]), k.sme_question])

    profile = requirement_profile(brd.requirements, anchors, needs, semantic)
    with open(f"{a.out}/requirement_profile.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(profile[0].keys()))
        w.writeheader(); w.writerows(profile)

    ranking = source_ranking(needs)
    summary = {"graph": {"nodes": G.number_of_nodes(), "edges": G.number_of_edges()},
               "anchors": sum(len(v) for v in anchors.values()),
               "anchors_ungrounded": sum(x.grounding == "NONE" for v in anchors.values() for x in v),
               "needs": len(needs),
               "levels": {l: sum(p["level"] == l for p in profile) for l in ("P0", "P1", "P2", "P3")},
               "needs_by_type": {}, "source_ranking": ranking,
               "lexical_uncovered": uncovered,
               "eval_deterministic_only": ev_det, "eval_with_semantic": ev_full,
               "semantic_provenance": (semantic or {}).get("_provenance", "none")}
    for k in needs:
        summary["needs_by_type"][k.knowledge_type] = summary["needs_by_type"].get(k.knowledge_type, 0) + 1
    with open(f"{a.out}/summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    print(f"Requirement levels: {summary['levels']}")
    print(f"Knowledge needs: {len(needs)}  by type: {summary['needs_by_type']}")
    if ev_det:
        for name, ev in (("deterministic only", ev_det), ("with semantic layer", ev_full)):
            print(f"[{name}] recall {ev['found']}/{ev['total']} = {ev['recall']:.0%}, "
                  f"precision {ev['precision']:.0%} of {ev['needs']} needs, by nature {ev['by_nature']}, missed {ev['missed']}")
    print("Top sources:", ranking[:5])


if __name__ == "__main__":
    main()
