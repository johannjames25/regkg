# Finding the hidden knowledge behind a BRD

A small prototype by Johann James.

A BRD for a regulatory report is never written from the regulation alone. Analysts add system details, product rules and past decisions, and much of that never gets written down. This prototype builds a knowledge graph from a regulation and its BRD, flags the parts of the BRD that neither document explains, and suggests where the missing knowledge probably lives.

![Knowledge graph](outputs/knowledge_graph.png)

*Left to right: regulation clauses, BRD requirements, knowledge gaps (yellow = names something we don't have, orange = unstated decision or number, red = conflicts with the regulation), and the likely source for each gap.*

## What it does

1. Links each BRD requirement to the regulation clauses it implements.
2. Pulls out every concrete detail in a requirement (tables, fields, systems, numbers, documents, decisions) and checks whether the regulation or the BRD explains it. Anything unexplained becomes a gap. This step uses rules only, no LLM.
3. An LLM step rewrites each requirement using only the regulation and compares it with the real one. The difference is the knowledge the business team added. This catches gaps the rules can't see.
4. Routes each gap to a likely internal source (data dictionary, policy document, compliance memo, decision log) with a question for an SME.

## Results on the sample data

The sample is a fictional large-exposures regulation (13 clauses) and a BRD written from it (11 requirements), with 18 gaps planted in advance as an answer key.

| Planted gaps | Count | Rules only | Rules + LLM |
|---|---|---|---|
| Visible in the text | 13 | 13 | 13 |
| Visible only through meaning | 5 | 0 | 5 |
| **Total** | **18** | **13 (72%)** | **18 (100%)** |

- The rules raised no false alarms.
- Only 1 of the 11 requirements traced fully back to the regulation.
- The LLM step also found 2 real gaps that weren't planted.

Example gap from `outputs/gaps.csv`:

| Requirement | Gap | Likely source | Question for an SME |
|---|---|---|---|
| BR-01 | Internal deadline of T+12 business days, while the regulation says 15 calendar days | Regulatory calendar / submission SOP | Is T+12 business days an internal buffer? It can land after the regulatory deadline. Which is binding? |

## Caveats

- The regulation, BRD and answer key are all synthetic and written by me, so this shows the method works end to end, not how accurate it is.
- The LLM outputs in `data/llm_cache.json` were produced by hand from the prompts in `regkg/semantic.py`, not from a live API run. The rules layer knows nothing about the answer key.

## Run it

```
pip install networkx matplotlib
python run.py                  # rules + cached LLM step
python run.py --llm none       # rules only
python run.py --llm anthropic  # live LLM (needs ANTHROPIC_API_KEY)
```

Outputs go to `outputs/`: `gaps.csv` (every gap with its source and SME question), `knowledge_graph.png`, `requirement_profile.csv` and `summary.json`.

## Files

- `data/regulation.md`, `data/brd.md`: the sample inputs
- `data/ground_truth.json`: the planted gaps
- `regkg/`: the pipeline (parse, anchors, coverage, semantic, knowledge, graph, evaluate)
- `run.py`: entry point
