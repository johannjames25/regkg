"""Parse a regulation and a BRD into structured units.

Real documents would come from a PDF parser (e.g. pdfplumber / docling) that keeps
clause numbering. The prototype uses markdown so the focus stays on the graph logic.
"""
import re
from dataclasses import dataclass, field


@dataclass
class Clause:
    id: str            # e.g. "§3.1"
    section: str       # e.g. "Reporting obligation"
    text: str
    kind: str = "provision"          # provision | definition | obligation | exemption
    defines: str | None = None       # term defined by a definition clause


@dataclass
class Requirement:
    id: str
    title: str
    text: str


@dataclass
class Brd:
    glossary: dict = field(default_factory=dict)   # term -> definition
    requirements: list = field(default_factory=list)


def parse_regulation(path):
    clauses, section = [], ""
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        m_sec = re.match(r"^§(\d+)\s+(.*)$", line)
        m_cl = re.match(r"^(\d+\.\d+)\s+(.*)$", line)
        if m_sec:
            section = m_sec.group(2)
        elif m_cl:
            text = m_cl.group(2)
            c = Clause(id=f"§{m_cl.group(1)}", section=section, text=text)
            m_def = re.match(r'^"([^"]+)"\s+means', text)
            if m_def:
                c.kind, c.defines = "definition", m_def.group(1)
            elif re.search(r"\bexempt|\bexcluded\b", text, re.I):
                c.kind = "exemption"
            elif re.search(r"\bshall\b|\bmay\b", text):
                c.kind = "obligation"
            clauses.append(c)
    return clauses


def parse_brd(path):
    brd, mode = Brd(), None
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line.lower().startswith("## glossary"):
            mode = "glossary"; continue
        if line.lower().startswith("## requirements"):
            mode = "req"; continue
        if mode == "glossary" and line.startswith("- "):
            term, _, definition = line[2:].partition(":")
            brd.glossary[term.strip()] = definition.strip()
        elif mode == "req":
            m = re.match(r"^(BR-\d+)\s+([^:]+):\s*(.*)$", line)
            if m:
                brd.requirements.append(Requirement(*m.groups()))
    return brd


def regulation_text(clauses):
    """Plain regulation text with clause numbers removed, so '4.2' etc. don't leak into grounding."""
    return " ".join(c.text for c in clauses)
