"""Build the three-layer knowledge graph and draw it."""
import json
import networkx as nx


def build_graph(clauses, brd, anchors_by_req, links, needs, semantic):
    G = nx.MultiDiGraph()
    for c in clauses:
        G.add_node(c.id, layer="regulation", type=c.kind, text=c.text, origin="REG")
    for term, d in brd.glossary.items():
        G.add_node(f"gl:{term}", layer="brd", type="glossary", text=d, origin="BRD")
    for r in brd.requirements:
        G.add_node(r.id, layer="brd", type="requirement", text=r.text, origin="BRD")
        for a in anchors_by_req[r.id]:
            nid = f"anchor:{a.kind}:{a.text[:40]}"
            G.add_node(nid, layer="bridge", type=a.kind, text=a.text, grounding=a.grounding)
            G.add_edge(r.id, nid, rel="mentions", origin="BRD")
            if a.grounding == "REG" and a.grounded_ref:
                G.add_edge(nid, a.grounded_ref, rel="grounded_in", origin="REG")
            elif a.grounding == "BRD" and a.grounded_ref.startswith("glossary:"):
                G.add_edge(nid, "gl:" + a.grounded_ref.split(":", 1)[1], rel="defined_by", origin="BRD")
    sem = (semantic or {}).get("requirements", {})
    for rid, cid, score in links:
        G.add_edge(rid, cid, rel="implements", origin="INFERRED", method="lexical", score=score)
    for rid, s in sem.items():
        for al in s.get("alignment", []):
            G.add_edge(rid, al["clause"], rel=al["relation"], origin="INFERRED", method="llm")
    for k in needs:
        G.add_node(k.id, layer="bridge", type="KnowledgeNeed", knowledge_type=k.knowledge_type,
                   level=k.level, text=k.description, conflict=k.conflict)
        G.add_edge(k.req, k.id, rel="requires", origin="INFERRED")
        if k.sources:
            src = f"src:{k.sources[0]}"
            G.add_node(src, layer="source", type="SourceType", text=k.sources[0])
            G.add_edge(k.id, src, rel="may_be_resolved_by", origin="INFERRED")
    return G


def export_json(G, path):
    data = nx.node_link_data(G, edges="edges")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, default=str)


def draw(G, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    cols = {"regulation": [], "requirement": [], "need": [], "source": []}
    for n, d in G.nodes(data=True):
        if d.get("layer") == "regulation": cols["regulation"].append(n)
        elif d.get("type") == "requirement": cols["requirement"].append(n)
        elif d.get("type") == "KnowledgeNeed": cols["need"].append(n)
        elif d.get("type") == "SourceType": cols["source"].append(n)
    H = G.subgraph([n for c in cols.values() for n in c])
    pos = {}
    for x, key in enumerate(["regulation", "requirement", "need", "source"]):
        nodes = sorted(cols[key], key=lambda n: (G.nodes[n].get("level", ""), n) if key == "need" else n)
        if key == "need":
            nodes = sorted(cols[key], key=lambda n: next(iter(G.predecessors(n)), ""))
        for i, n in enumerate(nodes):
            pos[n] = (x * 3.2, -i * (30 / max(len(nodes), 1)))
    colour = []
    for n in H.nodes:
        d = G.nodes[n]
        if d.get("layer") == "regulation": colour.append("#4C72B0")
        elif d.get("type") == "requirement": colour.append("#8172B2")
        elif d.get("type") == "SourceType": colour.append("#55A868")
        elif d.get("conflict"): colour.append("#C44E52")
        elif d.get("level") == "P3": colour.append("#DD8452")
        else: colour.append("#E6C229")
    plt.figure(figsize=(18, 13))
    edge_col = ["#C44E52" if d.get("rel") == "contradicts" else "#bbbbbb" for _, _, d in H.edges(data=True)]
    nx.draw_networkx_edges(H, pos, edge_color=edge_col, arrows=False, width=0.8, alpha=0.8)
    nx.draw_networkx_nodes(H, pos, node_color=colour, node_size=260)
    labels = {}
    for n in H.nodes:
        d = G.nodes[n]
        if d.get("type") == "KnowledgeNeed":
            labels[n] = f"{n} {d['knowledge_type'].replace('_', ' ').lower()} [{d['level']}]"
        elif d.get("type") == "SourceType":
            labels[n] = d["text"][:38]
        else:
            labels[n] = n
    lp = {n: (x + 0.18, y) for n, (x, y) in pos.items()}
    nx.draw_networkx_labels(H, lp, labels, font_size=7.5, horizontalalignment="left")
    for x, t in enumerate(["Regulation clauses", "BRD requirements", "Knowledge needs (gaps)", "Likely internal source"]):
        plt.text(x * 3.2, 1.6, t, fontsize=12, fontweight="bold")
    from matplotlib.patches import Patch
    plt.legend(handles=[Patch(color="#E6C229", label="P2 referenced but absent"),
                        Patch(color="#DD8452", label="P3 tacit"),
                        Patch(color="#C44E52", label="conflict with regulation")],
               loc="lower left", fontsize=9)
    plt.axis("off"); plt.xlim(-0.5, 13.5); plt.tight_layout()
    plt.savefig(path, dpi=130); plt.close()
