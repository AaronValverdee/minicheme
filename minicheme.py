#!/usr/bin/env python3
"""
Minicheme — Conceptual Chemical Process Planning CLI & Live Board Server.

One JSON file (`process.json`), one Python script (`minicheme.py`), one HTML page (`minicheme.html`).
Zero Obsidian. Zero JS build step. Token-optimized for AI agents and human chemical engineers.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import html
import importlib.util
import json
import os
import re
import socket
import sys
import tempfile
import threading
import time
import urllib.parse
import webbrowser
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

# Ensure UTF-8 output in Windows consoles
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

VERSION = "2.0.0"
DEFAULT_PORT = 8766
PROCESS_FILENAME = "process.json"

REPO_ROOT = Path(__file__).resolve().parent
HEURISTICS_PATH = REPO_ROOT / "resources" / "heuristics" / "heuristics.json"
PUBCHEM_FETCHER_PATH = REPO_ROOT / "resources" / "heuristics" / "pubchem_fetcher.py"
HTML_PATH = REPO_ROOT / "minicheme.html"

VALID_STATES = ("proposed", "todo", "doing", "review", "done")
ENGINEERING_STAGES = {"RX", "SP", "HX"}

DEFAULT_STAGES = [
    {"id": "BP", "name": "Basis & Properties", "color": "teal"},
    {"id": "RX", "name": "1. Reactor", "color": "blue"},
    {"id": "SP", "name": "2. Separation", "color": "violet"},
    {"id": "HX", "name": "3. Heat Exchangers", "color": "amber"},
    {"id": "SM", "name": "4. Conceptual Brief", "color": "emerald"},
]

DEFAULT_BLOCKS_BLUEPRINT = [
    {
        "id": "BP-01",
        "stage": "BP",
        "title": "Basis & Operating Mode",
        "deps": [],
        "objective": "Parse process inputs & ./references/, classify Continuous vs Batch (PROC-002), and capture capacity, specs, battery limits, and constraints.",
        "recommended_heuristics": ["PROC-001", "PROC-002", "PROC-003"],
    },
    {
        "id": "BP-02",
        "stage": "BP",
        "title": "Chemical Substances & Thermo Model",
        "deps": ["BP-01"],
        "objective": "Retrieve pure-component properties for 3-5 key species via `props`, rank normal boiling points / relative volatilities, flag azeotropes, and select the thermodynamic model.",
        "recommended_heuristics": ["PROP-001", "PROP-002", "PROC-003"],
    },
    {
        "id": "RX-01",
        "stage": "RX",
        "title": "Reactor Thermodynamics",
        "deps": ["BP-02"],
        "objective": "Quantify heat of reaction (ΔH_rxn), adiabatic temperature rise (ΔT_ad), thermal severity, equilibrium limits, and side reactions / extinction strategy.",
        "recommended_heuristics": ["REACT-004", "REACT-005", "PROC-004", "PROC-007"],
    },
    {
        "id": "RX-02",
        "stage": "RX",
        "title": "Reactor Type & Catalyst",
        "deps": ["RX-01"],
        "objective": "Select reactor family (PFR / fixed bed / CSTR / fluidized), catalyst class & particle size, and screen reactive separation alternatives.",
        "recommended_heuristics": ["REACT-003", "REACT-007", "PROC-008", "REACT-006"],
    },
    {
        "id": "RX-03",
        "stage": "RX",
        "title": "Reaction Conditions",
        "deps": ["RX-02"],
        "objective": "Set operating T, P (phase stability), stoichiometric ratio, space velocity / residence time, feed pressurization, and preliminary bed sizing.",
        "recommended_heuristics": ["REACT-002", "PROC-009", "REACT-007", "VES-001"],
    },
    {
        "id": "SP-01",
        "stage": "SP",
        "title": "Separation Steps & Sequence",
        "deps": ["RX-03"],
        "objective": "Synthesize separation train (flash, distillation, extraction, absorption) from relative volatilities, azeotropes, and recycle/purge structure.",
        "recommended_heuristics": ["DIST-001", "DIST-002", "EXTR-001", "EXTR-002", "PROC-005", "PROC-007"],
    },
    {
        "id": "SP-02",
        "stage": "SP",
        "title": "Separation Conditions",
        "deps": ["SP-01"],
        "objective": "Set column operating pressures (for CW condensation), T_top/T_bot, reflux ratio (1.2-1.3 R_min), theoretical stages, and tray vs packing internals.",
        "recommended_heuristics": ["DIST-003", "DIST-004", "DIST-005", "DIST-006", "EXTR-003", "EXTR-004"],
    },
    {
        "id": "HX-01",
        "stage": "HX",
        "title": "Heat Exchanger Types",
        "deps": ["SP-02"],
        "objective": "List primary heat-transfer services, select TEMA configurations & standard geometry, allocate tube vs shell fluids, and verify reboiler nucleate-boiling ΔT.",
        "recommended_heuristics": ["HEX-001", "HEX-002", "HEX-007", "HEX-010"],
    },
    {
        "id": "HX-02",
        "stage": "HX",
        "title": "Utilities & Pinch",
        "deps": ["HX-01"],
        "objective": "Identify process-to-process heat recovery matches, set ΔT_min, verify pinch discipline, and specify cooling water / steam utility headers.",
        "recommended_heuristics": ["PROC-010", "HEX-004", "UTIL-REF-001", "UTIL-REF-003"],
    },
    {
        "id": "SM-01",
        "stage": "SM",
        "title": "Conceptual Process Brief",
        "deps": ["HX-02"],
        "objective": "Synthesize a 1-page executive brief (Capacity, Reaction, Separation, Energy) confirming readiness to build the Aspen Plus / HYSYS / DWSIM model.",
        "recommended_heuristics": ["PROC-001", "PROC-002", "PROC-010"],
    },
]

STAGE_DEFAULT_FAMILIES = {
    "BP": ["process_synthesis_and_strategy", "physical_properties_and_shortcuts"],
    "RX": ["reactors_and_kinetics", "process_synthesis_and_strategy", "pressure_vessels_and_storage"],
    "SP": ["separations_distillation_and_absorption", "separations_liquid_liquid_extraction", "separations_solids_and_slurries"],
    "HX": ["heat_transfer_exchangers_and_furnaces", "cooling_towers_and_refrigeration", "process_synthesis_and_strategy"],
    "SM": ["process_synthesis_and_strategy"],
}


class MinichemeError(Exception):
    """Domain or workflow rule violation."""


# ---------------------------------------------------------------------------
# Heuristics Engine (compact, zero-bloat queries & strict validation)
# ---------------------------------------------------------------------------

_HEURISTICS_CACHE: dict[str, Any] | None = None


def load_heuristics_db() -> dict[str, Any]:
    """Load and index resources/heuristics/heuristics.json once per process."""
    global _HEURISTICS_CACHE
    if _HEURISTICS_CACHE is not None:
        return _HEURISTICS_CACHE
    if not HEURISTICS_PATH.exists():
        _HEURISTICS_CACHE = {"metadata": {}, "families": {}, "by_id": {}}
        return _HEURISTICS_CACHE
    data = json.loads(HEURISTICS_PATH.read_text(encoding="utf-8"))
    by_id: dict[str, dict[str, Any]] = {}
    for fam_key, fam_val in data.get("families", {}).items():
        for rule in fam_val.get("rules", []):
            rid = str(rule.get("id", "")).upper()
            if rid:
                entry = dict(rule)
                entry["_family_key"] = fam_key
                entry["_family_name"] = fam_val.get("name", fam_key)
                by_id[rid] = entry
    _HEURISTICS_CACHE = {
        "metadata": data.get("metadata", {}),
        "families": data.get("families", {}),
        "by_id": by_id,
    }
    return _HEURISTICS_CACHE


def primary_citation(rule: dict[str, Any]) -> str:
    refs = rule.get("references") or []
    if not refs:
        return "Minicheme Heuristics DB"
    r0 = refs[0]
    parts = [str(r0.get("source", "")).strip()]
    sec = r0.get("table_or_section")
    if sec:
        parts.append(str(sec).strip())
    pg = r0.get("page")
    if pg is not None and str(pg).strip():
        parts.append(f"p. {pg}")
    return ", ".join(p for p in parts if p)


def compact_rule_text(rule: dict[str, Any]) -> str:
    """Render one heuristic in ~50-80 tokens for agent consumption."""
    rid = rule["id"]
    sub = rule.get("subfamily_or_equipment", "")
    rtxt = rule.get("rule", "").strip()
    quant = rule.get("quantitative_guidelines") or {}
    q_parts = []
    for k, v in list(quant.items())[:5]:
        if isinstance(v, (dict, list)):
            v_str = json.dumps(v, ensure_ascii=False)
            if len(v_str) > 90:
                v_str = v_str[:87] + "..."
        else:
            v_str = str(v)
        q_parts.append(f"{k}={v_str}")
    lim = str(rule.get("conditions_and_limitations", "")).strip()
    if len(lim) > 150:
        lim = lim[:147] + "..."
    cite = primary_citation(rule)
    lines = [f"[{rid}] ({sub}) {rtxt}"]
    if q_parts:
        lines.append("  Params: " + "; ".join(q_parts))
    if lim:
        lines.append("  Limits: " + lim)
    lines.append("  Source: " + cite)
    return "\n".join(lines)


def search_heuristics(
    ids: list[str] | None = None,
    family: str | None = None,
    query: str | None = None,
    limit: int = 12,
) -> list[dict[str, Any]]:
    db = load_heuristics_db()
    by_id = db["by_id"]
    if ids:
        out = []
        missing = []
        for raw in ids:
            rid = raw.strip().upper()
            if rid in by_id:
                out.append(by_id[rid])
            else:
                missing.append(raw)
        if missing:
            raise MinichemeError(
                f"Unknown heuristic ID(s): {', '.join(missing)}. Run `heuristics --search <keyword>` to find valid IDs."
            )
        return out

    pool = list(by_id.values())
    if family:
        fk = family.strip().lower()
        pool = [
            r
            for r in pool
            if fk in r.get("_family_key", "").lower() or fk in r.get("_family_name", "").lower()
        ]
    if query:
        terms = [t.lower() for t in re.split(r"\s+", query.strip()) if t]
        scored = []
        for r in pool:
            hay = " ".join(
                [
                    r.get("id", ""),
                    r.get("subfamily_or_equipment", ""),
                    r.get("rule", ""),
                    " ".join(r.get("tags") or []),
                    r.get("explanation_and_derivation", ""),
                ]
            ).lower()
            score = sum(3 if t in r.get("id", "").lower() or t in " ".join(r.get("tags") or []).lower() else (2 if t in r.get("rule", "").lower() else (1 if t in hay else 0)) for t in terms)
            if score > 0:
                scored.append((score, r))
        scored.sort(key=lambda x: (-x[0], x[1]["id"]))
        pool = [r for _, r in scored]
    return pool[:limit]


def hydrate_heuristics(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate heuristic IDs against heuristics.json and auto-fill canonical summary & source."""
    db = load_heuristics_db()
    by_id = db["by_id"]
    hydrated = []
    seen = set()
    for item in items:
        if isinstance(item, str):
            if ":" in item:
                rid, applied = item.split(":", 1)
            else:
                rid, applied = item, ""
            item = {"id": rid.strip(), "applied": applied.strip()}
        rid = str(item.get("id", "")).strip().upper()
        if not rid:
            continue
        if by_id and rid not in by_id:
            # Suggest close matches from same prefix
            prefix = rid.split("-")[0]
            suggestions = [k for k in sorted(by_id) if k.startswith(prefix)][:6]
            hint = f" Valid `{prefix}` IDs: {', '.join(suggestions)}" if suggestions else ""
            raise MinichemeError(f"Unknown heuristic ID '{rid}'. Every heuristic must exist in resources/heuristics/heuristics.json.{hint}")
        if rid in seen:
            continue
        seen.add(rid)
        rule = by_id.get(rid)
        summary = str(item.get("summary") or "").strip()
        source = str(item.get("source") or "").strip()
        if rule:
            if not summary:
                rtxt = rule.get("rule", "").strip()
                summary = rtxt if len(rtxt) <= 130 else rtxt[:127].rstrip() + "..."
            if not source:
                source = primary_citation(rule)
        hydrated.append(
            {
                "id": rid,
                "summary": summary,
                "applied": str(item.get("applied") or "").strip(),
                "source": source,
            }
        )
    return hydrated


# ---------------------------------------------------------------------------
# Process Board Model, Canonical JSON & Safe Atomic I/O
# ---------------------------------------------------------------------------

def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_process(title: str = "New Chemical Process", description: str = "", yolo_all: bool = False) -> dict[str, Any]:
    blocks = []
    for bp in DEFAULT_BLOCKS_BLUEPRINT:
        blk: dict[str, Any] = {
            "id": bp["id"],
            "stage": bp["stage"],
            "title": bp["title"],
            "state": "todo",
            "deps": list(bp["deps"]),
            "objective": bp["objective"],
            "recommended_heuristics": list(bp["recommended_heuristics"]),
            "proposal": "",
            "rationale": "",
            "parameters": [],
            "heuristics": [],
            "notes": [],
        }
        if yolo_all and bp["id"] == "SM-01":
            blk["yolo"] = True
        blocks.append(blk)

    return canonical(
        {
            "minicheme": 2,
            "title": title.strip() or "New Chemical Process",
            "basis": {
                "description": description.strip(),
                "target_product": "",
                "feedstocks": "",
                "capacity": "",
                "operating_hours": 8000,
                "operating_mode": "",
                "product_spec": "",
                "thermo_model": "",
                "battery_limits": "",
                "constraints": "",
                "references": [],
            },
            "substances": [],
            "azeotrope_notes": "",
            "stages": [dict(s) for s in DEFAULT_STAGES],
            "blocks": blocks,
        }
    )


def _ordered(obj: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    out = {}
    for k in keys:
        if k in obj:
            out[k] = obj[k]
    for k, v in obj.items():
        if k not in out:
            out[k] = v
    return out


def canonical_note(n: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "at": str(n.get("at") or now_iso()),
        "by": str(n.get("by") or "agent"),
        "text": str(n.get("text") or "").strip(),
    }
    if n.get("kind") and n.get("kind") != "note":
        out["kind"] = str(n["kind"])
    if n.get("missing"):
        out["missing"] = str(n["missing"]).strip()
    if n.get("why"):
        out["why"] = str(n["why"]).strip()
    if n.get("baseline"):
        out["baseline"] = str(n["baseline"]).strip()
    if n.get("edited"):
        out["edited"] = str(n["edited"])
    return _ordered(out, ("at", "by", "kind", "text", "missing", "why", "baseline", "edited"))


def canonical_block(b: dict[str, Any]) -> dict[str, Any]:
    state = str(b.get("state") or "todo").strip().lower()
    if state not in VALID_STATES:
        state = "todo"
    deps = []
    for d in b.get("deps") or []:
        ds = str(d).strip()
        if ds and ds not in deps and ds != b.get("id"):
            deps.append(ds)
    params = []
    for p in b.get("parameters") or []:
        if isinstance(p, dict) and str(p.get("name", "")).strip():
            params.append(
                _ordered(
                    {
                        "name": str(p.get("name", "")).strip(),
                        "value": str(p.get("value", "")).strip(),
                        "unit": str(p.get("unit", "")).strip(),
                        "note": str(p.get("note", "")).strip(),
                    },
                    ("name", "value", "unit", "note"),
                )
            )
    heurs = []
    for h in b.get("heuristics") or []:
        if isinstance(h, dict) and str(h.get("id", "")).strip():
            heurs.append(
                _ordered(
                    {
                        "id": str(h.get("id", "")).strip().upper(),
                        "summary": str(h.get("summary", "")).strip(),
                        "applied": str(h.get("applied", "")).strip(),
                        "source": str(h.get("source", "")).strip(),
                    },
                    ("id", "summary", "applied", "source"),
                )
            )
    notes = [canonical_note(n) for n in (b.get("notes") or []) if isinstance(n, dict) and str(n.get("text", "")).strip()]

    out: dict[str, Any] = {
        "id": str(b.get("id", "")).strip(),
        "stage": str(b.get("stage", "")).strip(),
        "title": str(b.get("title", "")).strip(),
        "state": state,
        "deps": deps,
        "objective": str(b.get("objective", "")).strip(),
    }
    rec = [str(r).strip().upper() for r in (b.get("recommended_heuristics") or []) if str(r).strip()]
    if rec:
        out["recommended_heuristics"] = rec
    if str(b.get("proposal", "")).strip():
        out["proposal"] = str(b.get("proposal", "")).strip()
    if str(b.get("rationale", "")).strip():
        out["rationale"] = str(b.get("rationale", "")).strip()
    if params:
        out["parameters"] = params
    if heurs:
        out["heuristics"] = heurs
    if str(b.get("mermaid", "")).strip():
        out["mermaid"] = str(b.get("mermaid", "")).strip()
    if b.get("yolo"):
        out["yolo"] = True
    if b.get("yolo_before"):
        out["yolo_before"] = True
    if isinstance(b.get("started"), dict) and b["started"].get("by"):
        out["started"] = {"at": str(b["started"].get("at") or now_iso()), "by": str(b["started"]["by"])}
    if b.get("at"):
        out["at"] = str(b["at"])
    if b.get("by"):
        out["by"] = str(b["by"])
    if notes:
        out["notes"] = notes
    for k, v in b.items():
        if k not in out and k not in (
            "proposal",
            "rationale",
            "parameters",
            "heuristics",
            "notes",
            "recommended_heuristics",
            "mermaid",
            "yolo",
            "yolo_before",
            "started",
            "at",
            "by",
        ):
            out[k] = v
    return _ordered(
        out,
        (
            "id",
            "stage",
            "title",
            "state",
            "deps",
            "yolo",
            "yolo_before",
            "at",
            "by",
            "started",
            "objective",
            "recommended_heuristics",
            "proposal",
            "rationale",
            "parameters",
            "heuristics",
            "mermaid",
            "notes",
        ),
    )


def _clean_num(val: Any) -> Any:
    """Match JS JSON.stringify number formatting (40.0 -> 40) for byte-identical diffs."""
    if isinstance(val, float) and val.is_integer():
        return int(val)
    return val


def canonical(board: dict[str, Any]) -> dict[str, Any]:
    basis_in = board.get("basis") if isinstance(board.get("basis"), dict) else {}
    refs = [str(r).strip() for r in (basis_in.get("references") or []) if str(r).strip()]
    basis = _ordered(
        {
            "description": str(basis_in.get("description") or "").strip(),
            "target_product": str(basis_in.get("target_product") or "").strip(),
            "feedstocks": str(basis_in.get("feedstocks") or "").strip(),
            "capacity": str(basis_in.get("capacity") or "").strip(),
            "operating_hours": basis_in.get("operating_hours", 8000),
            "operating_mode": str(basis_in.get("operating_mode") or "").strip(),
            "product_spec": str(basis_in.get("product_spec") or "").strip(),
            "thermo_model": str(basis_in.get("thermo_model") or "").strip(),
            "battery_limits": str(basis_in.get("battery_limits") or "").strip(),
            "constraints": str(basis_in.get("constraints") or "").strip(),
            "references": refs,
        },
        (
            "description",
            "target_product",
            "feedstocks",
            "capacity",
            "operating_hours",
            "operating_mode",
            "product_spec",
            "thermo_model",
            "battery_limits",
            "constraints",
            "references",
        ),
    )

    stages = []
    for s in board.get("stages") or DEFAULT_STAGES:
        if isinstance(s, dict) and str(s.get("id", "")).strip():
            stages.append(
                _ordered(
                    {
                        "id": str(s["id"]).strip(),
                        "name": str(s.get("name") or s["id"]).strip(),
                        "color": str(s.get("color") or "blue").strip(),
                    },
                    ("id", "name", "color"),
                )
            )

    substances = []
    for c in board.get("substances") or []:
        if isinstance(c, dict) and str(c.get("common_name") or c.get("name") or "").strip():
            substances.append(
                _ordered(
                    {
                        "name": str(c.get("name") or c.get("common_name")).strip(),
                        "common_name": str(c.get("common_name") or c.get("name")).strip(),
                        "role": str(c.get("role") or "").strip(),
                        "formula": str(c.get("formula") or "N/A").strip(),
                        "cas": str(c.get("cas") or "N/A").strip(),
                        "mw": str(c.get("mw") or "N/A").strip(),
                        "bp_c": _clean_num(c.get("bp_c")),
                        "bp_k": _clean_num(c.get("bp_k")),
                        "mp_c": _clean_num(c.get("mp_c")),
                        "tc_c": _clean_num(c.get("tc_c")),
                        "pc_bar": _clean_num(c.get("pc_bar")),
                        "omega": str(c.get("omega") or "N/A").strip(),
                        "density": str(c.get("density") or "N/A").strip(),
                        "viscosity": str(c.get("viscosity") or "N/A").strip(),
                        "vp": str(c.get("vp") or "N/A").strip(),
                        "cid": str(c.get("cid") or "N/A").strip(),
                    },
                    (
                        "name",
                        "common_name",
                        "role",
                        "formula",
                        "cas",
                        "mw",
                        "bp_c",
                        "bp_k",
                        "mp_c",
                        "tc_c",
                        "pc_bar",
                        "omega",
                        "density",
                        "viscosity",
                        "vp",
                        "cid",
                    ),
                )
            )

    blocks = [canonical_block(b) for b in (board.get("blocks") or []) if isinstance(b, dict) and str(b.get("id", "")).strip()]

    out: dict[str, Any] = {
        "minicheme": int(board.get("minicheme") or 2),
        "title": str(board.get("title") or "Untitled Process").strip(),
        "basis": basis,
        "substances": substances,
        "azeotrope_notes": str(board.get("azeotrope_notes") or "").strip(),
        "stages": stages,
        "blocks": blocks,
    }
    for k, v in board.items():
        if k not in out:
            out[k] = v
    return _ordered(out, ("minicheme", "title", "basis", "substances", "azeotrope_notes", "stages", "blocks"))


def dumps(board: dict[str, Any]) -> str:
    return json.dumps(canonical(board), indent=2, ensure_ascii=False) + "\n"


def etag_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def load_process(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise MinichemeError(f"Process file not found: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MinichemeError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(raw, dict) or "blocks" not in raw:
        raise MinichemeError(f"Not a valid Minicheme process.json: {path}")
    return canonical(raw)


@contextlib.contextmanager
def file_lock(path: Path, timeout: float = 5.0):
    lock_path = path.parent / f".{path.name}.lock"
    deadline = time.monotonic() + timeout
    fd = None
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{os.getpid()}\n".encode("ascii"))
            break
        except FileExistsError:
            # Break stale locks older than 30s
            try:
                if time.time() - lock_path.stat().st_mtime > 30:
                    lock_path.unlink(missing_ok=True)
                    continue
            except OSError:
                pass
            if time.monotonic() > deadline:
                raise MinichemeError(f"Could not acquire lock on {path} within {timeout}s")
            time.sleep(0.03)
    try:
        yield
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".minicheme-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def mutate_process(path: Path, fn) -> tuple[dict[str, Any], Any]:
    with file_lock(path):
        board = load_process(path)
        result = fn(board)
        text = dumps(board)
        write_atomic(path, text)
        return canonical(board), result


# ---------------------------------------------------------------------------
# Graph, Dependencies, Waiting, YOLO & Validation Logic
# ---------------------------------------------------------------------------

def block_map(board: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {b["id"]: b for b in board.get("blocks", [])}


def find_block(board: dict[str, Any], ref: str) -> dict[str, Any]:
    r = ref.strip().upper()
    for b in board.get("blocks", []):
        if b["id"].upper() == r:
            return b
    raise MinichemeError(f"Block '{ref}' not found. Available: {', '.join(b['id'] for b in board.get('blocks', []))}")


def find_stage(board: dict[str, Any], ref: str) -> dict[str, Any]:
    r = ref.strip().lower()
    for s in board.get("stages", []):
        if s["id"].lower() == r or s["name"].lower() == r:
            return s
    raise MinichemeError(f"Stage '{ref}' not found. Available: {', '.join(s['id'] for s in board.get('stages', []))}")


def unmet_deps(block: dict[str, Any], bmap: dict[str, dict[str, Any]]) -> list[str]:
    return [d for d in block.get("deps", []) if d in bmap and bmap[d]["state"] != "done"]


def open_question(block: dict[str, Any]) -> dict[str, Any] | None:
    """Return the latest unresolved `ask` note if no later note answered it."""
    notes = block.get("notes") or []
    for n in reversed(notes):
        kind = n.get("kind", "note")
        if kind == "ask":
            return n
        if kind in ("answer", "note", "review", "feedback", "plan"):
            return None
    return None


def change_request(block: dict[str, Any]) -> dict[str, Any] | None:
    if block.get("state") != "proposed":
        return None
    for n in reversed(block.get("notes") or []):
        if n.get("kind") == "changes":
            return n
        if n.get("by") != "human":
            return None
    return None


def view_state(block: dict[str, Any], bmap: dict[str, dict[str, Any]]) -> str:
    st = block["state"]
    if st == "todo" and unmet_deps(block, bmap):
        return "blocked"
    if st == "doing" and open_question(block):
        return "waiting"
    return st


def _upstream_ids(bmap: dict[str, dict[str, Any]], start_id: str) -> set[str]:
    seen: set[str] = set()
    stack = list(bmap[start_id].get("deps", []))
    while stack:
        cur = stack.pop()
        if cur in seen or cur not in bmap:
            continue
        seen.add(cur)
        stack.extend(bmap[cur].get("deps", []))
    return seen


def yolo_cover(board: dict[str, Any]) -> dict[str, str]:
    """
    Map block_id -> 'auto' (finish straight to done) or 'target' (finish goes to review)
    or 'stop' (yolo_before stop marker; upstream is 'auto').
    Mirrors Kanvas YOLO semantics.
    """
    bmap = block_map(board)
    cover: dict[str, str] = {}
    active_targets = [
        b for b in board.get("blocks", []) if b.get("yolo") and b["state"] not in ("review", "done")
    ]
    active_stops = [
        b for b in board.get("blocks", []) if b.get("yolo_before") and b["state"] not in ("review", "done")
    ]
    # Mark targets and their upstreams
    target_set = {b["id"] for b in active_targets}
    for b in active_targets:
        cover.setdefault(b["id"], "target")
        for up in _upstream_ids(bmap, b["id"]):
            cover[up] = "auto"
    for b in active_stops:
        if b["id"] not in cover:
            cover[b["id"]] = "stop"
        for up in _upstream_ids(bmap, b["id"]):
            if cover.get(up) != "auto":
                cover[up] = "auto"
    # If a target is upstream of another target, outer target takes over
    for tid in list(target_set):
        for other in target_set:
            if other != tid and tid in _upstream_ids(bmap, other):
                cover[tid] = "auto"
    return cover


def reaches(board: dict[str, Any], start: str, goal: str) -> bool:
    bmap = block_map(board)
    seen: set[str] = set()
    stack = [start]
    while stack:
        cur = stack.pop()
        if cur == goal:
            return True
        if cur in seen or cur not in bmap:
            continue
        seen.add(cur)
        stack.extend(bmap[cur].get("deps", []))
    return False


def find_cycles(board: dict[str, Any]) -> list[list[str]]:
    bmap = block_map(board)
    color: dict[str, int] = {}
    path: list[str] = []
    cycles: list[list[str]] = []

    def dfs(u: str):
        color[u] = 1
        path.append(u)
        for v in bmap[u].get("deps", []):
            if v not in bmap:
                continue
            if color.get(v, 0) == 1:
                idx = path.index(v)
                cycles.append(path[idx:] + [v])
            elif color.get(v, 0) == 0:
                dfs(v)
        path.pop()
        color[u] = 2

    for bid in bmap:
        if color.get(bid, 0) == 0:
            dfs(bid)
    return cycles


def validate_board(board: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    stages = {s["id"] for s in board.get("stages", [])}
    seen_ids: set[str] = set()
    bmap = block_map(board)
    db = load_heuristics_db()
    valid_h = db["by_id"]

    for b in board.get("blocks", []):
        bid = b.get("id", "")
        if not bid:
            errs.append("Block with empty id")
            continue
        if bid in seen_ids:
            errs.append(f"Duplicate block id: {bid}")
        seen_ids.add(bid)
        if b.get("stage") and b["stage"] not in stages:
            errs.append(f"{bid}: unknown stage '{b['stage']}'")
        for d in b.get("deps", []):
            if d not in bmap:
                errs.append(f"{bid}: missing dependency '{d}'")
            if d == bid:
                errs.append(f"{bid}: self-dependency")
        for h in b.get("heuristics", []):
            hid = str(h.get("id", "")).upper()
            if valid_h and hid not in valid_h:
                errs.append(f"{bid}: unknown heuristic ID '{hid}'")

    for cyc in find_cycles(board):
        errs.append("Dependency cycle: " + " -> ".join(cyc))
    return errs


def next_block_id(board: dict[str, Any], stage_id: str) -> str:
    prefix = stage_id.upper()
    max_n = 0
    pat = re.compile(rf"^{re.escape(prefix)}-(\d+)$", re.I)
    for b in board.get("blocks", []):
        m = pat.match(b["id"])
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"{prefix}-{max_n + 1:02d}"


def append_note(block: dict[str, Any], text: str, by: str = "agent", kind: str = "note", **extra: Any) -> dict[str, Any]:
    note: dict[str, Any] = {"at": now_iso(), "by": by, "text": text.strip()}
    if kind != "note":
        note["kind"] = kind
    for k, v in extra.items():
        if v:
            note[k] = str(v).strip()
    block.setdefault("notes", []).append(note)
    return note


# ---------------------------------------------------------------------------
# Chemical Properties Engine (delegates to resources/heuristics/pubchem_fetcher.py)
# ---------------------------------------------------------------------------

def _load_fetcher_module():
    if not PUBCHEM_FETCHER_PATH.exists():
        raise MinichemeError(f"Property fetcher not found at {PUBCHEM_FETCHER_PATH}")
    spec = importlib.util.spec_from_file_location("minicheme_pubchem_fetcher", str(PUBCHEM_FETCHER_PATH))
    if spec is None or spec.loader is None:
        raise MinichemeError("Could not load pubchem_fetcher.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _parse_num(s: Any) -> float | None:
    if isinstance(s, (int, float)):
        return float(s)
    if not isinstance(s, str):
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", s.replace("−", "-"))
    return float(m.group(0)) if m else None


def fetch_substances(names: list[str], roles: list[str] | None = None) -> list[dict[str, Any]]:
    mod = _load_fetcher_module()
    roles = roles or []
    out = []
    for idx, raw_name in enumerate(names[:8]):
        role = roles[idx].strip() if idx < len(roles) else ""
        if ":" in raw_name and not role:
            nm, role = raw_name.split(":", 1)
            nm, role = nm.strip(), role.strip()
        else:
            nm = raw_name.strip()
        prof = mod.get_compound_profile(nm)
        bp_c = _parse_num(prof.get("bp"))
        bp_k = prof.get("bp_k")
        if bp_k is None and bp_c is not None:
            bp_k = round(bp_c + 273.15, 2)
        elif bp_k is not None:
            bp_k = round(float(bp_k), 2)
        out.append(
            {
                "name": nm,
                "common_name": prof.get("common_name") or nm,
                "role": role,
                "formula": prof.get("formula", "N/A"),
                "cas": prof.get("cas", "N/A"),
                "mw": prof.get("mw", "N/A"),
                "bp_c": round(bp_c, 1) if bp_c is not None else None,
                "bp_k": bp_k,
                "mp_c": _parse_num(prof.get("mp")),
                "tc_c": _parse_num(prof.get("tc")),
                "pc_bar": _parse_num(prof.get("pc")),
                "omega": prof.get("omega", "N/A"),
                "density": prof.get("density", "N/A"),
                "viscosity": prof.get("viscosity", "N/A"),
                "vp": prof.get("vp", "N/A"),
                "cid": prof.get("cid", "N/A"),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Process Discovery & Path Resolution
# ---------------------------------------------------------------------------

def resolve_process_path(arg_path: str | None = None, must_exist: bool = True) -> Path:
    raw = arg_path or os.environ.get("MINICHEME_PROCESS")
    if raw:
        p = Path(raw).expanduser()
        if p.is_dir():
            p = p / PROCESS_FILENAME
        if must_exist and not p.exists():
            raise MinichemeError(f"Process file not found: {p}")
        return p.resolve()

    # Search cwd and parents
    cur = Path.cwd().resolve()
    for d in [cur, *cur.parents]:
        cand = d / PROCESS_FILENAME
        if cand.exists():
            return cand
        if d == REPO_ROOT:
            break

    # If in repo root and there is only one process workspace, pick it
    found = discover_processes(REPO_ROOT)
    if len(found) == 1:
        return found[0]
    if must_exist:
        hint = (
            " Specify `-p <folder>` or run from a process folder. Available: "
            + ", ".join(str(p.parent.relative_to(REPO_ROOT)) for p in found)
            if found
            else " Run `python minicheme.py init <ProcessName>` to create one."
        )
        raise MinichemeError(f"No {PROCESS_FILENAME} found in {cur}.{hint}")
    return cur / PROCESS_FILENAME


def discover_processes(root: Path | None = None) -> list[Path]:
    base = (root or REPO_ROOT).resolve()
    found: list[Path] = []
    direct = base / PROCESS_FILENAME
    if direct.exists():
        found.append(direct)
    for child in sorted(base.iterdir()):
        if not child.is_dir() or child.name.startswith(".") or child.name in ("resources", "tests", "__pycache__"):
            continue
        p = child / PROCESS_FILENAME
        if p.exists():
            found.append(p)
        # Also allow processes/<name>/process.json
        if child.name in ("processes", "examples"):
            for sub in sorted(child.iterdir()):
                if sub.is_dir() and (sub / PROCESS_FILENAME).exists():
                    found.append(sub / PROCESS_FILENAME)
    return found


# ---------------------------------------------------------------------------
# Compact Agent-Optimized CLI Formatting & Commands
# ---------------------------------------------------------------------------

def _gist(text: str, maxlen: int = 120) -> str:
    line = " ".join(text.strip().splitlines())
    return line if len(line) <= maxlen else line[: maxlen - 3].rstrip() + "..."


def _read_text_arg(val: str | None, use_stdin: bool = False, file_path: str | None = None) -> str:
    if use_stdin:
        return sys.stdin.read()
    if file_path:
        return Path(file_path).read_text(encoding="utf-8")
    return val or ""


def cmd_init(args: argparse.Namespace) -> None:
    target = Path(args.dir).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    pfile = target / PROCESS_FILENAME
    if pfile.exists() and not args.force:
        raise MinichemeError(f"{pfile} already exists. Use --force to overwrite.")
    title = args.title or target.name.replace("_", " ").replace("-", " ").title()
    desc = args.desc or ""
    if args.from_md:
        md_path = Path(args.from_md).expanduser().resolve()
        if not md_path.exists():
            raise MinichemeError(f"Input markdown not found: {md_path}")
        desc = md_path.read_text(encoding="utf-8").strip()
    elif (target / "Process design.md").exists() and not desc:
        desc = (target / "Process design.md").read_text(encoding="utf-8").strip()

    refs_dir = target / "references"
    refs_dir.mkdir(exist_ok=True)
    refs = [f"references/{f.name}" for f in sorted(refs_dir.iterdir()) if f.is_file() and f.name.lower() != "readme.md"]

    board = new_process(title=title, description=desc, yolo_all=args.yolo)
    board["basis"]["references"] = refs
    write_atomic(pfile, dumps(board))
    print(f"Initialized Minicheme workspace: {pfile}")
    print(f"  Title : {board['title']}")
    print(f"  Blocks: {len(board['blocks'])} (Douglas hierarchy BP -> RX -> SP -> HX -> SM)")
    if args.yolo:
        print("  YOLO  : enabled up to SM-01 (autonomous chain ending at Conceptual Brief review)")
    print(f"Next: python minicheme.py serve \"{target}\"  |  python minicheme.py next -p \"{target}\"")


def cmd_status(args: argparse.Namespace) -> None:
    path = resolve_process_path(args.process)
    board = load_process(path)
    bmap = block_map(board)
    cover = yolo_cover(board)
    blocks = board["blocks"]
    done_n = sum(1 for b in blocks if b["state"] == "done")
    pct = int(round(100 * done_n / len(blocks))) if blocks else 0

    print(f"{board['title']}  [{done_n}/{len(blocks)} done, {pct}%]  ({path})")
    basis = board.get("basis", {})
    summary_bits = [x for x in (basis.get("capacity"), basis.get("operating_mode"), basis.get("thermo_model")) if x]
    if summary_bits:
        print("Basis: " + " | ".join(summary_bits))
    if board.get("substances"):
        print("Substances: " + ", ".join(f"{c['common_name']} (Tb={c['bp_c']}°C)" if c.get("bp_c") is not None else c["common_name"] for c in board["substances"]))

    buckets: dict[str, list[dict[str, Any]]] = {
        "waiting": [],
        "doing": [],
        "review": [],
        "ready": [],
        "blocked": [],
        "proposed": [],
        "done": [],
    }
    for b in blocks:
        vs = view_state(b, bmap)
        if vs == "todo":
            buckets["ready"].append(b)
        else:
            buckets[vs].append(b)

    for label, key in [
        ("WAITING FOR HUMAN", "waiting"),
        ("DOING", "doing"),
        ("REVIEW", "review"),
        ("READY", "ready"),
        ("PROPOSED", "proposed"),
        ("BLOCKED", "blocked"),
        ("DONE", "done"),
    ]:
        items = buckets[key]
        if not items:
            continue
        print(f"\n{label} ({len(items)}):")
        for b in items:
            tags = []
            if cover.get(b["id"]) == "auto":
                tags.append("YOLO")
            elif cover.get(b["id"]) == "target":
                tags.append("YOLO-REVIEW")
            elif cover.get(b["id"]) == "stop":
                tags.append("YOLO-STOP")
            if key == "blocked":
                tags.append("waits:" + ",".join(unmet_deps(b, bmap)))
            if key == "waiting":
                q = open_question(b)
                if q:
                    tags.append(f"Q: {_gist(q['text'], 70)}")
            if key == "proposed":
                cr = change_request(b)
                if cr:
                    tags.append(f"changes: {_gist(cr['text'], 60)}")
            tag_str = f"  [{' | '.join(tags)}]" if tags else ""
            print(f"  {b['id']:6s} {b['title']}{tag_str}")

    errs = validate_board(board)
    if errs:
        print("\nPROBLEMS:")
        for e in errs:
            print(f"  - {e}")


def cmd_next(args: argparse.Namespace) -> None:
    """
    Token-optimized single-shot briefing for AI agents!
    Returns exact active/next block + compact upstream context + compact heuristics (~300 tokens).
    """
    path = resolve_process_path(args.process)
    board = load_process(path)
    bmap = block_map(board)
    cover = yolo_cover(board)
    blocks = board["blocks"]
    done_n = sum(1 for b in blocks if b["state"] == "done")
    print(f"PROCESS: {board['title']} ({done_n}/{len(blocks)} done)")

    # Check waiting questions first
    waiting = [b for b in blocks if view_state(b, bmap) == "waiting"]
    if waiting:
        print("\nACTION: STOP — Waiting for human answer:")
        for b in waiting:
            q = open_question(b)
            print(f"  {b['id']} ({b['title']}): {q['text'] if q else ''}")
        print("Ask the human in chat or wait for their reply in the browser.")
        return

    # Check review items if not in YOLO auto mode
    review = [b for b in blocks if b["state"] == "review"]
    doing = [b for b in blocks if view_state(b, bmap) == "doing"]
    ready = [b for b in blocks if view_state(b, bmap) == "todo"]

    target = doing[0] if doing else (ready[0] if ready else None)
    if target is None:
        if review:
            print("\nACTION: STOP — Waiting for human review:")
            for b in review:
                print(f"  {b['id']} ({b['title']})")
            return
        proposed = [b for b in blocks if b["state"] == "proposed"]
        if proposed:
            print("\nACTION: STOP — Waiting for human approval of proposals:")
            for b in proposed:
                print(f"  {b['id']} ({b['title']})")
            return
        print("\nALL BLOCKS DONE! Conceptual planning complete — ready for process simulator.")
        return

    # Basis summary (compact)
    basis = board.get("basis", {})
    print("\nBASIS:")
    for k in ("target_product", "feedstocks", "capacity", "operating_mode", "product_spec", "thermo_model", "constraints"):
        if basis.get(k):
            print(f"  {k}: {basis[k]}")
    if basis.get("references"):
        print("  references: " + ", ".join(basis["references"]))
    if basis.get("description") and target["id"] == "BP-01":
        print("  user_input: " + _gist(basis["description"], 500))

    if board.get("substances"):
        print("\nSUBSTANCES:")
        for c in board["substances"]:
            bp = f"{c['bp_c']}°C" if c.get("bp_c") is not None else "N/A"
            print(f"  - {c['common_name']} ({c['formula']}, MW={c['mw']}, Tb={bp}, rho={c['density']}, Psat={c['vp']})" + (f" [{c['role']}]" if c.get("role") else ""))
        if board.get("azeotrope_notes"):
            print("  azeotropes: " + _gist(board["azeotrope_notes"], 200))

    # Active or Next block
    ymode = cover.get(target["id"])
    y_str = f"  [{ymode.upper()}]" if ymode else ""
    print(f"\nNEXT BLOCK: {target['id']} — {target['title']} (state={target['state']}{y_str})")
    print(f"OBJECTIVE: {target.get('objective', '')}")

    # Check if sent back
    for n in reversed(target.get("notes") or []):
        if n.get("kind") == "feedback" or n.get("text", "").startswith("Sent back:"):
            print(f"REVIEW FEEDBACK TO ADDRESS: {n['text']}")
            break

    # Upstream decisions (compact!)
    if target.get("deps"):
        print("\nUPSTREAM DECISIONS:")
        for did in target["deps"]:
            up = bmap.get(did)
            if not up:
                continue
            print(f"  {did} ({up['title']}): {_gist(up.get('proposal', ''), 200)}")
            if up.get("parameters"):
                p_inline = "; ".join(f"{p['name']}={p['value']} {p['unit']}".strip() for p in up["parameters"][:6])
                print(f"    Params: {p_inline}")

    # Recommended heuristics straight from heuristics.json (compact!)
    rec_ids = target.get("recommended_heuristics") or []
    db = load_heuristics_db()
    if rec_ids and db["by_id"]:
        print("\nRELEVANT HEURISTICS (verified from heuristics.json):")
        for rid in rec_ids:
            rule = db["by_id"].get(rid.upper())
            if rule:
                print(compact_rule_text(rule))

    # Concrete next command hint
    rel_p = str(path.parent)
    print("\nWORKFLOW COMMANDS:")
    if target["state"] == "todo":
        print(f"  1. python minicheme.py start {target['id']} -p \"{rel_p}\" -m \"Plan: ...\"")
    if target["id"] == "BP-01":
        print(f"  2. python minicheme.py basis -p \"{rel_p}\" --target ... --capacity ... --mode Continuous --spec ... --thermo ...")
    elif target["id"] == "BP-02":
        print(f"  2. python minicheme.py props \"Reactant1:Reactant\" \"Product:Product\" \"Solvent:Solvent\" -p \"{rel_p}\"")
    print(f"  3. If critical data missing: python minicheme.py ask {target['id']} -p \"{rel_p}\" \"Question\" --missing \"...\" --why \"...\" --baseline \"...\"")
    print(f"  4. When solved: python minicheme.py finish {target['id']} -p \"{rel_p}\" --stdin <<'EOF'\n     {{\"proposal\":\"...\",\"rationale\":\"...\",\"parameters\":[{{\"name\":\"...\",\"value\":\"...\",\"unit\":\"...\",\"note\":\"...\"}}],\"heuristics\":[{{\"id\":\"...\",\"applied\":\"...\"}}],\"summary\":\"...\"}}\n     EOF")


def cmd_show(args: argparse.Namespace) -> None:
    path = resolve_process_path(args.process)
    board = load_process(path)
    bmap = block_map(board)
    b = find_block(board, args.id)
    vs = view_state(b, bmap)
    print(f"{b['id']} — {b['title']}  [{vs}]  (stage={b['stage']})")
    if b.get("deps"):
        print("Deps: " + ", ".join(f"{d} ({bmap[d]['state']})" if d in bmap else d for d in b["deps"]))
    if b.get("objective"):
        print(f"Objective: {b['objective']}")
    if b.get("proposal"):
        print(f"\n--- Proposal ---\n{b['proposal']}")
    if b.get("parameters"):
        print("\n--- Parameters ---")
        for p in b["parameters"]:
            print(f"  - {p['name']}: {p['value']} {p['unit']}  ({p['note']})" if p["note"] else f"  - {p['name']}: {p['value']} {p['unit']}")
    if b.get("rationale"):
        print(f"\n--- Rationale ---\n{b['rationale']}")
    if b.get("heuristics"):
        print("\n--- Heuristics ---")
        for h in b["heuristics"]:
            print(f"  - [{h['id']}] {h['summary']} | Applied: {h['applied']} ({h['source']})")
    if b.get("notes"):
        print("\n--- Notes ---")
        for n in b["notes"]:
            kind = f" [{n['kind']}]" if n.get("kind") else ""
            print(f"  {n['at']} {n['by']}{kind}: {n['text']}")


def cmd_heuristics(args: argparse.Namespace) -> None:
    db = load_heuristics_db()
    if args.families:
        print(f"Heuristics Families ({len(db['families'])} families, {len(db['by_id'])} rules):")
        for fk, fv in db["families"].items():
            ids = [r["id"] for r in fv.get("rules", [])]
            print(f"  {fk} ({len(ids)}): {', '.join(ids)}")
        return

    ids = list(args.ids or [])
    family = args.family
    if args.block:
        path = resolve_process_path(args.process)
        board = load_process(path)
        blk = find_block(board, args.block)
        ids = blk.get("recommended_heuristics") or []
        if not ids:
            fams = STAGE_DEFAULT_FAMILIES.get(blk["stage"], [])
            family = fams[0] if fams else None

    rules = search_heuristics(ids=ids or None, family=family, query=args.search, limit=args.limit)
    if not rules:
        print("No matching heuristics found.")
        return
    if args.json:
        print(json.dumps(rules, indent=2, ensure_ascii=False))
        return
    for r in rules:
        print(compact_rule_text(r))
        print()


def cmd_props(args: argparse.Namespace) -> None:
    path = resolve_process_path(args.process)
    roles = [r.strip() for r in args.roles.split(",")] if args.roles else []
    substances = fetch_substances(args.compounds, roles=roles)

    def _update(board: dict[str, Any]):
        if args.append:
            existing = {c["common_name"].lower(): c for c in board.get("substances", [])}
            for c in substances:
                existing[c["common_name"].lower()] = c
            board["substances"] = list(existing.values())
        else:
            board["substances"] = substances
        if args.azeotropes:
            board["azeotrope_notes"] = args.azeotropes.strip()
        if args.thermo:
            board.setdefault("basis", {})["thermo_model"] = args.thermo.strip()

    board, _ = mutate_process(path, _update)
    print(f"Updated {len(board['substances'])} substances in {path.name}:")
    ordered = sorted(board["substances"], key=lambda x: x["bp_k"] if x.get("bp_k") is not None else 99999)
    for i, c in enumerate(ordered, 1):
        bp = f"{c['bp_c']}°C" if c.get("bp_c") is not None else "N/A"
        print(f"  {i}. {c['common_name']:14s} {c['formula']:8s} MW={c['mw']:6s} Tb={bp:8s} Tc={c['tc_c']}°C Pc={c['pc_bar']}bar rho={c['density']} Psat={c['vp']}")


def cmd_basis(args: argparse.Namespace) -> None:
    path = resolve_process_path(args.process)

    def _update(board: dict[str, Any]):
        if args.title:
            board["title"] = args.title.strip()
        b = board.setdefault("basis", {})
        mapping = {
            "description": args.desc,
            "target_product": args.target,
            "feedstocks": args.feedstocks,
            "capacity": args.capacity,
            "operating_mode": args.mode,
            "product_spec": args.spec,
            "thermo_model": args.thermo,
            "battery_limits": args.battery_limits,
            "constraints": args.constraints,
        }
        for k, v in mapping.items():
            if v is not None:
                b[k] = v.strip()
        if args.hours is not None:
            b["operating_hours"] = args.hours
        if args.azeotropes is not None:
            board["azeotrope_notes"] = args.azeotropes.strip()

    board, _ = mutate_process(path, _update)
    print(f"Updated Basis of Design for '{board['title']}'.")


def cmd_start(args: argparse.Namespace) -> None:
    path = resolve_process_path(args.process)
    who = args.agent or os.environ.get("MINICHEME_AGENT") or "agent"

    def _update(board: dict[str, Any]):
        bmap = block_map(board)
        blk = find_block(board, args.id)
        if blk["state"] == "done":
            raise MinichemeError(f"{blk['id']} is already done.")
        if blk["state"] == "proposed":
            raise MinichemeError(f"{blk['id']} is still proposed. Ask the human to approve it in the browser first.")
        if blk["state"] == "review":
            raise MinichemeError(f"{blk['id']} is waiting for human review.")
        unmet = unmet_deps(blk, bmap)
        if unmet:
            raise MinichemeError(f"{blk['id']} is blocked by unfinished dependency: {', '.join(unmet)}")
        blk["state"] = "doing"
        blk["started"] = {"at": now_iso(), "by": who}
        msg = _read_text_arg(args.message, args.stdin, args.file).strip()
        if msg:
            append_note(blk, msg, by=who, kind="plan")
        return blk["id"]

    _, bid = mutate_process(path, _update)
    print(f"Started {bid} (doing, by {who}).")


def cmd_ask(args: argparse.Namespace) -> None:
    path = resolve_process_path(args.process)
    who = args.agent or os.environ.get("MINICHEME_AGENT") or "agent"
    question = _read_text_arg(args.question, args.stdin, args.file).strip()
    if not question:
        raise MinichemeError("Question text is required.")

    def _update(board: dict[str, Any]):
        blk = find_block(board, args.id)
        if blk["state"] not in ("doing", "todo"):
            raise MinichemeError(f"Cannot ask on {blk['id']} in state '{blk['state']}'.")
        blk["state"] = "doing"
        append_note(
            blk,
            question,
            by=who,
            kind="ask",
            missing=args.missing or "",
            why=args.why or "",
            baseline=args.baseline or "",
        )
        return blk["id"]

    _, bid = mutate_process(path, _update)
    print(f"Waiting for human on {bid}: {question}")


def cmd_answer(args: argparse.Namespace) -> None:
    path = resolve_process_path(args.process)
    who = args.agent or "human"
    text = _read_text_arg(args.text, args.stdin, args.file).strip()
    if not text:
        raise MinichemeError("Answer text is required.")

    def _update(board: dict[str, Any]):
        blk = find_block(board, args.id)
        append_note(blk, text, by=who, kind="answer")
        return blk["id"]

    _, bid = mutate_process(path, _update)
    print(f"Recorded answer on {bid}.")


def cmd_note(args: argparse.Namespace) -> None:
    path = resolve_process_path(args.process)
    who = args.agent or os.environ.get("MINICHEME_AGENT") or "agent"
    text = _read_text_arg(args.text, args.stdin, args.file).strip()
    if not text:
        raise MinichemeError("Note text is required.")

    def _update(board: dict[str, Any]):
        blk = find_block(board, args.id)
        append_note(blk, text, by=who, kind="note")
        return blk["id"]

    _, bid = mutate_process(path, _update)
    print(f"Added note to {bid}.")


def cmd_pause(args: argparse.Namespace) -> None:
    path = resolve_process_path(args.process)
    who = args.agent or os.environ.get("MINICHEME_AGENT") or "agent"

    def _update(board: dict[str, Any]):
        blk = find_block(board, args.id)
        if blk["state"] != "doing":
            raise MinichemeError(f"{blk['id']} is not doing (current: {blk['state']}).")
        blk["state"] = "todo"
        blk.pop("started", None)
        msg = _read_text_arg(args.message, args.stdin, args.file).strip()
        if msg:
            append_note(blk, msg, by=who, kind="note")
        return blk["id"]

    _, bid = mutate_process(path, _update)
    print(f"Paused {bid} (back to todo).")


def _parse_param_flag(raw: str) -> dict[str, str]:
    parts = [p.strip() for p in raw.split("|")]
    while len(parts) < 4:
        parts.append("")
    return {"name": parts[0], "value": parts[1], "unit": parts[2], "note": parts[3]}


def cmd_finish(args: argparse.Namespace) -> None:
    path = resolve_process_path(args.process)
    who = args.agent or os.environ.get("MINICHEME_AGENT") or "agent"

    payload: dict[str, Any] = {}
    if args.stdin or args.json_file:
        raw_text = sys.stdin.read() if args.stdin else Path(args.json_file).read_text(encoding="utf-8")
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise MinichemeError(f"Invalid JSON payload for finish: {exc}") from exc
        if not isinstance(payload, dict):
            raise MinichemeError("finish JSON payload must be an object.")

    proposal = (args.proposal if args.proposal is not None else payload.get("proposal", "")).strip()
    rationale = (args.rationale if args.rationale is not None else payload.get("rationale", "")).strip()
    summary = (args.message if args.message is not None else payload.get("summary", "")).strip()
    mermaid = (args.mermaid if args.mermaid is not None else payload.get("mermaid", "")).strip()

    params_raw = list(payload.get("parameters") or [])
    for pf in args.param or []:
        params_raw.append(_parse_param_flag(pf))

    heurs_raw = list(payload.get("heuristics") or [])
    for hf in args.heuristic or []:
        heurs_raw.append(hf)

    hydrated_heurs = hydrate_heuristics(heurs_raw)

    def _update(board: dict[str, Any]):
        bmap = block_map(board)
        blk = find_block(board, args.id)
        if blk["state"] not in ("doing", "todo"):
            raise MinichemeError(f"Cannot finish {blk['id']} from state '{blk['state']}'. Start it first.")
        unmet = unmet_deps(blk, bmap)
        if unmet:
            raise MinichemeError(f"{blk['id']} is blocked by unfinished dependency: {', '.join(unmet)}")
        if open_question(blk):
            raise MinichemeError(f"{blk['id']} has an unanswered question. Record the human's answer before finishing.")

        if proposal:
            blk["proposal"] = proposal
        if rationale:
            blk["rationale"] = rationale
        if params_raw:
            blk["parameters"] = params_raw
        if hydrated_heurs:
            blk["heuristics"] = hydrated_heurs
        if mermaid:
            blk["mermaid"] = mermaid

        # Enforce concrete chemical-engineering deliverable
        if not str(blk.get("proposal", "")).strip():
            raise MinichemeError(f"{blk['id']} requires a non-empty `proposal` (conceptual design decision).")
        if blk["stage"] in ENGINEERING_STAGES:
            if not str(blk.get("rationale", "")).strip():
                raise MinichemeError(f"{blk['id']} ({blk['stage']}) requires a non-empty first-principles `rationale`.")
            if not blk.get("heuristics"):
                raise MinichemeError(
                    f"{blk['id']} ({blk['stage']}) requires at least one verified heuristic ID from resources/heuristics/heuristics.json."
                )
        rev_summary = summary or _gist(blk["proposal"], 180)

        cover = yolo_cover(board)
        ymode = cover.get(blk["id"])
        if ymode == "auto":
            blk["state"] = "done"
            new_state = "done (YOLO)"
        else:
            blk["state"] = "review"
            new_state = "review"
            if blk.get("yolo"):
                blk.pop("yolo", None)
        blk.pop("started", None)
        append_note(blk, rev_summary, by=who, kind="review")
        return blk["id"], new_state

    _, (bid, new_state) = mutate_process(path, _update)
    print(f"Finished {bid} -> {new_state}.")


def cmd_accept(args: argparse.Namespace) -> None:
    """Human CLI shortcut to approve/accept a block (mark done) or send it back."""
    path = resolve_process_path(args.process)

    def _update(board: dict[str, Any]):
        blk = find_block(board, args.id)
        if args.send_back:
            blk["state"] = "todo"
            blk.pop("started", None)
            append_note(blk, f"Sent back: {args.send_back.strip()}", by="human", kind="feedback")
            return blk["id"], "todo (sent back)"
        if blk["state"] == "proposed":
            blk["state"] = "todo"
            return blk["id"], "todo (approved)"
        blk["state"] = "done"
        blk.pop("started", None)
        if args.note:
            append_note(blk, args.note.strip(), by="human", kind="note")
        return blk["id"], "done"

    _, (bid, st) = mutate_process(path, _update)
    print(f"{bid} -> {st}.")


def cmd_yolo(args: argparse.Namespace) -> None:
    """Human CLI shortcut to toggle YOLO on a block (auto-approving upstream proposals)."""
    path = resolve_process_path(args.process)

    def _update(board: dict[str, Any]):
        bmap = block_map(board)
        blk = find_block(board, args.id)
        if args.off:
            blk.pop("yolo", None)
            blk.pop("yolo_before", None)
            return blk["id"], "off"
        if args.before:
            blk.pop("yolo", None)
            blk["yolo_before"] = True
            mode = "yolo_before"
        else:
            blk.pop("yolo_before", None)
            blk["yolo"] = True
            mode = "yolo"
        # Approve upstream proposals (and target if yolo)
        up = _upstream_ids(bmap, blk["id"])
        if mode == "yolo":
            up.add(blk["id"])
        for uid in up:
            ub = bmap[uid]
            if ub["state"] == "proposed":
                ub["state"] = "todo"
            elif ub["state"] == "review" and uid != blk["id"]:
                ub["state"] = "done"
        return blk["id"], mode

    _, (bid, mode) = mutate_process(path, _update)
    print(f"YOLO on {bid}: {mode}.")


def cmd_propose(args: argparse.Namespace) -> None:
    path = resolve_process_path(args.process)
    who = args.agent or os.environ.get("MINICHEME_AGENT") or "agent"

    def _update(board: dict[str, Any]):
        stage = find_stage(board, args.stage)
        bmap = block_map(board)
        deps = []
        for d in args.deps or []:
            deps.append(find_block(board, d)["id"])
        bid = next_block_id(board, stage["id"])
        blk = canonical_block(
            {
                "id": bid,
                "stage": stage["id"],
                "title": args.title,
                "state": "proposed",
                "deps": deps,
                "objective": args.objective or "",
                "recommended_heuristics": args.heuristics or [],
                "at": now_iso(),
                "by": who,
            }
        )
        board["blocks"].append(blk)
        return bid

    _, bid = mutate_process(path, _update)
    print(f"Proposed {bid}: {args.title} (waiting for human approval).")


def cmd_depend(args: argparse.Namespace) -> None:
    path = resolve_process_path(args.process)

    def _update(board: dict[str, Any]):
        blk = find_block(board, args.id)
        added = []
        for dep_ref in args.on:
            dep = find_block(board, dep_ref)
            if dep["id"] == blk["id"]:
                raise MinichemeError(f"{blk['id']} cannot depend on itself.")
            if reaches(board, dep["id"], blk["id"]):
                raise MinichemeError(f"Adding {blk['id']} -> {dep['id']} would create a cycle.")
            if dep["id"] not in blk["deps"]:
                blk["deps"].append(dep["id"])
                added.append(dep["id"])
        return blk["id"], added

    _, (bid, added) = mutate_process(path, _update)
    print(f"{bid} now depends on: {', '.join(added) if added else '(already linked)'}")


def cmd_check(args: argparse.Namespace) -> None:
    path = resolve_process_path(args.process)
    board = load_process(path)
    errs = validate_board(board)
    if errs:
        print(f"FAIL ({len(errs)} error(s)) in {path}:")
        for e in errs:
            print(f"  - {e}")
        sys.exit(1)
    print(f"OK: {path} ({len(board['blocks'])} blocks, {len(board['substances'])} substances, 0 errors).")


# ---------------------------------------------------------------------------
# Export (Standalone Self-Contained HTML Snapshot & Markdown Brief)
# ---------------------------------------------------------------------------

def render_markdown_brief(board: dict[str, Any]) -> str:
    bmap = block_map(board)
    basis = board.get("basis", {})
    done_n = sum(1 for b in board["blocks"] if b["state"] == "done")
    lines = [
        f"# Conceptual Process Brief: {board['title']}",
        "",
        f"> **Status**: {done_n}/{len(board['blocks'])} blocks completed  ",
    ]
    if basis.get("capacity"):
        lines.append(f"> **Capacity**: {basis['capacity']} ({basis.get('operating_hours', 8000)} h/yr, {basis.get('operating_mode', 'TBD')})  ")
    if basis.get("product_spec"):
        lines.append(f"> **Product Spec**: {basis['product_spec']}  ")
    if basis.get("thermo_model"):
        lines.append(f"> **Thermodynamic Model**: {basis['thermo_model']}  ")
    lines.append("")

    if board.get("substances"):
        lines += [
            "## Chemical Substances",
            "",
            "| Substance | Role | Formula | CAS | MW | Normal B.P. | $T_c$ | $P_c$ | Density | $P^{\\text{sat}}$ (25°C) |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
        for c in board["substances"]:
            bp = f"{c['bp_c']} °C" if c.get("bp_c") is not None else "N/A"
            tc = f"{c['tc_c']} °C" if c.get("tc_c") is not None else "N/A"
            pc = f"{c['pc_bar']} bar" if c.get("pc_bar") is not None else "N/A"
            lines.append(
                f"| **{c['common_name']}** | {c.get('role','')} | `{c['formula']}` | {c['cas']} | {c['mw']} | {bp} | {tc} | {pc} | {c['density']} | {c['vp']} |"
            )
        if board.get("azeotrope_notes"):
            lines += ["", f"> **Azeotrope / Phase Note**: {board['azeotrope_notes']}"]
        lines.append("")

    for stage in board.get("stages", []):
        sblocks = [b for b in board["blocks"] if b["stage"] == stage["id"]]
        if not sblocks:
            continue
        lines += [f"## {stage['name']}", ""]
        for b in sblocks:
            vs = view_state(b, bmap)
            lines.append(f"### {b['id']}: {b['title']} (`{vs}`)")
            if b.get("proposal"):
                lines += ["", b["proposal"]]
            if b.get("parameters"):
                lines += ["", "| Parameter | Value | Unit | Notes |", "| :--- | :--- | :--- | :--- |"]
                for p in b["parameters"]:
                    lines.append(f"| {p['name']} | {p['value']} | {p['unit']} | {p['note']} |")
            if b.get("rationale"):
                lines += ["", "**First-Principles Rationale**", "", b["rationale"]]
            if b.get("heuristics"):
                lines += ["", "| Heuristic | Rule Summary | Application | Source |", "| :--- | :--- | :--- | :--- |"]
                for h in b["heuristics"]:
                    lines.append(f"| `{h['id']}` | {h['summary']} | {h['applied']} | {h['source']} |")
            lines.append("")

    return "\n".join(lines).strip() + "\n"


def export_html_snapshot(board: dict[str, Any], out_path: Path) -> None:
    if not HTML_PATH.exists():
        raise MinichemeError(f"HTML template not found: {HTML_PATH}")
    template = HTML_PATH.read_text(encoding="utf-8")
    db = load_heuristics_db()
    # Embed only heuristics referenced in board (plus recommended) to keep snapshot super compact!
    ref_ids = set()
    for b in board.get("blocks", []):
        for h in b.get("heuristics", []):
            ref_ids.add(h["id"])
        for r in b.get("recommended_heuristics", []):
            ref_ids.add(r)
    embedded_h = {rid: db["by_id"][rid] for rid in sorted(ref_ids) if rid in db["by_id"]}
    payload = {"board": canonical(board), "heuristics": embedded_h}
    safe_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    marker = '<script id="minicheme-snapshot" type="application/json"></script>'
    if marker not in template:
        raise MinichemeError("Snapshot injection marker missing from minicheme.html")
    rendered = template.replace(
        marker,
        f'<script id="minicheme-snapshot" type="application/json">{safe_json}</script>',
        1,
    )
    write_atomic(out_path, rendered)


def cmd_export(args: argparse.Namespace) -> None:
    path = resolve_process_path(args.process)
    board = load_process(path)
    if args.md:
        out = Path(args.out) if args.out else path.parent / "Process Summary.md"
        write_atomic(out, render_markdown_brief(board))
        print(f"Exported Markdown brief to {out}")
    else:
        out = Path(args.out) if args.out else path.parent / f"{path.parent.name}_snapshot.html"
        export_html_snapshot(board, out)
        print(f"Exported standalone HTML snapshot to {out}")


# ---------------------------------------------------------------------------
# Legacy Obsidian Workspace Migration
# ---------------------------------------------------------------------------

def _extract_section(md: str, heading_pattern: str) -> str:
    m = re.search(rf"^##\s+{heading_pattern}[^\n]*\n(.*?)(?=^##\s+|\Z)", md, re.M | re.S | re.I)
    return m.group(1).strip() if m else ""


def _extract_heuristics_from_md(md: str) -> list[dict[str, str]]:
    sec = _extract_section(md, r"3\.\s+Justifying Heuristic")
    if not sec:
        return []
    found = []
    for line in sec.splitlines():
        if not line.strip().startswith("|") or "---" in line or "Heuristic ID" in line:
            continue
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cols) >= 3:
            ids = re.findall(r"[A-Z]+(?:-[A-Z]+)*-\d{3}", cols[0])
            for rid in ids:
                found.append({"id": rid, "applied": cols[2]})
    return hydrate_heuristics(found) if found else []


def migrate_obsidian_workspace(old_dir: Path) -> dict[str, Any]:
    old_dir = old_dir.resolve()
    title = old_dir.name.replace("_", " ").strip()
    desc = ""
    pd_file = old_dir / "Process design.md"
    if pd_file.exists():
        desc = pd_file.read_text(encoding="utf-8").strip()

    board = new_process(title=title, description=desc)

    # References
    refs_dir = old_dir / "references"
    if refs_dir.exists():
        board["basis"]["references"] = [
            f"references/{f.name}" for f in sorted(refs_dir.iterdir()) if f.is_file() and f.name.lower() != "readme.md"
        ]

    # Map old canvas colors if present
    canvas_states: dict[str, str] = {}
    canvas_file = old_dir / "Unit operations.canvas"
    file_to_id = {
        "1.1 Reactor - Thermodynamics.md": "RX-01",
        "1.2 Reactor - Type.md": "RX-02",
        "1.3 Reactor - Reaction conditions.md": "RX-03",
        "2.1 Separation - Steps and sequence.md": "SP-01",
        "2.2 Separation - Conditions.md": "SP-02",
        "3.1 Heat exchangers - Types.md": "HX-01",
        "3.2 Heat exchangers - Utilities and pinch.md": "HX-02",
    }
    if canvas_file.exists():
        try:
            cdata = json.loads(canvas_file.read_text(encoding="utf-8"))
            for node in cdata.get("nodes", []):
                fn = node.get("file")
                if fn in file_to_id:
                    col = str(node.get("color", "1"))
                    canvas_states[file_to_id[fn]] = "done" if col == "4" else ("doing" if col == "5" else "todo")
        except Exception:
            pass

    bmap = block_map(board)
    solved_any = False
    for fname, bid in file_to_id.items():
        fpath = old_dir / fname
        if not fpath.exists():
            continue
        md = fpath.read_text(encoding="utf-8")
        if "[Pending" in md or "Status: Pending" in md or "Status: Unsolved" in md:
            continue
        prop = _extract_section(md, r"1\.\s+[^\n]*Proposal")
        rat = _extract_section(md, r"2\.\s+First-Principles")
        heurs = _extract_heuristics_from_md(md)
        if prop and "[Pending" not in prop:
            solved_any = True
            bmap[bid]["proposal"] = prop
            bmap[bid]["rationale"] = rat
            bmap[bid]["heuristics"] = heurs
            bmap[bid]["state"] = canvas_states.get(bid, "done")
            append_note(bmap[bid], "Migrated from legacy Minicheme Obsidian note.", by="migration", kind="note")

    # Summary
    sum_file = old_dir / "Process Summary.md"
    if sum_file.exists():
        smd = sum_file.read_text(encoding="utf-8").strip()
        m_title = re.search(r"^#\s+Process Summary:\s*(.+)$", smd, re.M)
        if m_title:
            board["title"] = m_title.group(1).strip()
        bmap["SM-01"]["proposal"] = smd
        bmap["SM-01"]["state"] = "done" if all(bmap[x]["state"] == "done" for x in file_to_id.values()) else "todo"

    if solved_any:
        bmap["BP-01"]["state"] = "done"
        bmap["BP-02"]["state"] = "done"

    return canonical(board)


def cmd_migrate(args: argparse.Namespace) -> None:
    src = Path(args.dir).expanduser().resolve()
    if not src.is_dir():
        raise MinichemeError(f"Directory not found: {src}")
    board = migrate_obsidian_workspace(src)
    out = Path(args.out).expanduser().resolve() if args.out else src / PROCESS_FILENAME
    write_atomic(out, dumps(board))
    done_n = sum(1 for b in board["blocks"] if b["state"] == "done")
    print(f"Migrated '{src.name}' -> {out} ({done_n}/{len(board['blocks'])} blocks done).")


# ---------------------------------------------------------------------------
# Live Multi-Process HTTP Server (Compare-and-Swap + ETag Polling)
# ---------------------------------------------------------------------------

class MinichemeServer(ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(self, server_address, root_dir: Path, initial_paths: list[Path]):
        super().__init__(server_address, MinichemeHandler)
        self.root_dir = root_dir.resolve()
        self.boards_lock = threading.Lock()
        self.boards: dict[str, Path] = {}
        for p in initial_paths:
            self.register_board(p)

    def _slug_for(self, path: Path) -> str:
        parent = path.parent.resolve()
        if parent == self.root_dir:
            base = parent.name
        else:
            try:
                base = str(parent.relative_to(self.root_dir)).replace("\\", "-").replace("/", "-")
            except ValueError:
                base = parent.name
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", base).strip("-").lower() or "process"
        return slug

    def register_board(self, path: Path) -> str:
        path = path.resolve()
        with self.boards_lock:
            for k, v in self.boards.items():
                if v == path:
                    return k
            slug = self._slug_for(path)
            cand = slug
            i = 2
            while cand in self.boards:
                cand = f"{slug}-{i}"
                i += 1
            self.boards[cand] = path
            return cand

    def refresh_discovered(self) -> None:
        for p in discover_processes(self.root_dir):
            self.register_board(p)
        # Drop deleted files cleanly
        with self.boards_lock:
            for k in [k for k, p in self.boards.items() if not p.exists()]:
                self.boards.pop(k, None)

    def list_boards(self) -> list[dict[str, Any]]:
        self.refresh_discovered()
        items = []
        with self.boards_lock:
            snap = list(self.boards.items())
        for slug, path in snap:
            try:
                b = load_process(path)
                done = sum(1 for x in b["blocks"] if x["state"] == "done")
                total = len(b["blocks"])
                bmap = block_map(b)
                waiting = sum(1 for x in b["blocks"] if view_state(x, bmap) == "waiting")
                review = sum(1 for x in b["blocks"] if x["state"] == "review")
                items.append(
                    {
                        "slug": slug,
                        "title": b["title"],
                        "path": str(path),
                        "done": done,
                        "total": total,
                        "waiting": waiting,
                        "review": review,
                    }
                )
            except Exception:
                items.append({"slug": slug, "title": slug, "path": str(path), "done": 0, "total": 0, "waiting": 0, "review": 0})
        return items


class MinichemeHandler(BaseHTTPRequestHandler):
    server: MinichemeServer

    def log_message(self, fmt: str, *args: Any) -> None:
        # Quiet console output
        return

    def _send_bytes(self, status: int, body: bytes, content_type: str, headers: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if headers:
            for k, v in headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, data: Any, headers: dict[str, str] | None = None) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._send_bytes(status, body, "application/json; charset=utf-8", headers)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length > 0 else b""

    def do_GET(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        p = parsed.path

        if p == "/api/health":
            self._send_json(200, {"ok": True, "version": VERSION})
            return

        if p == "/api/boards":
            self._send_json(200, {"boards": self.server.list_boards()})
            return

        if p == "/api/heuristics":
            db = load_heuristics_db()
            self._send_json(200, {"metadata": db["metadata"], "families": db["families"]})
            return

        if p == "/" or p == "/index.html":
            boards = self.server.list_boards()
            if boards:
                self.send_response(302)
                self.send_header("Location", f"/{boards[0]['slug']}/")
                self.end_headers()
                return
            # Serve app directly in empty state
            self._serve_html()
            return

        # Match /<slug>/api/board or /<slug>/api/export/md or /<slug>/
        parts = [seg for seg in p.split("/") if seg]
        if not parts:
            self._send_json(404, {"error": "Not found"})
            return

        slug = parts[0]
        self.server.refresh_discovered()
        bpath = self.server.boards.get(slug)
        if bpath is None:
            self._send_json(404, {"error": f"Unknown process board '{slug}'"})
            return

        if len(parts) == 1:
            if not p.endswith("/"):
                self.send_response(302)
                self.send_header("Location", f"/{slug}/")
                self.end_headers()
                return
            self._serve_html()
            return

        sub = "/".join(parts[1:])
        if sub == "api/board":
            try:
                board = load_process(bpath)
                text = dumps(board)
                tag = etag_of(text)
                if self.headers.get("If-None-Match") == tag:
                    self._send_bytes(304, b"", "application/json; charset=utf-8", {"ETag": tag})
                    return
                self._send_bytes(200, text.encode("utf-8"), "application/json; charset=utf-8", {"ETag": tag})
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
            return

        if sub == "api/export/md":
            board = load_process(bpath)
            md = render_markdown_brief(board).encode("utf-8")
            self._send_bytes(
                200,
                md,
                "text/markdown; charset=utf-8",
                {"Content-Disposition": f'attachment; filename="{slug}_brief.md"'},
            )
            return

        if sub == "api/export/html":
            board = load_process(bpath)
            with tempfile.TemporaryDirectory() as td:
                out = Path(td) / "snap.html"
                export_html_snapshot(board, out)
                data = out.read_bytes()
            self._send_bytes(
                200,
                data,
                "text/html; charset=utf-8",
                {"Content-Disposition": f'attachment; filename="{slug}_snapshot.html"'},
            )
            return

        # Any other path under /<slug>/ serves minicheme.html
        self._serve_html()

    def _serve_html(self) -> None:
        if not HTML_PATH.exists():
            self._send_bytes(500, b"minicheme.html not found", "text/plain; charset=utf-8")
            return
        self._send_bytes(200, HTML_PATH.read_bytes(), "text/html; charset=utf-8")

    def do_PUT(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        parts = [seg for seg in parsed.path.split("/") if seg]
        if len(parts) == 3 and parts[1] == "api" and parts[2] == "board":
            slug = parts[0]
            bpath = self.server.boards.get(slug)
            if bpath is None:
                self._send_json(404, {"error": f"Unknown board '{slug}'"})
                return
            try:
                incoming = json.loads(self._read_body().decode("utf-8"))
                if not isinstance(incoming, dict) or "blocks" not in incoming:
                    self._send_json(400, {"error": "Invalid board JSON"})
                    return
                expected_etag = self.headers.get("If-Match")
                with file_lock(bpath):
                    cur_board = load_process(bpath)
                    cur_text = dumps(cur_board)
                    cur_tag = etag_of(cur_text)
                    if expected_etag and expected_etag != cur_tag:
                        self._send_bytes(409, cur_text.encode("utf-8"), "application/json; charset=utf-8", {"ETag": cur_tag})
                        return
                    new_board = canonical(incoming)
                    new_text = dumps(new_board)
                    write_atomic(bpath, new_text)
                    new_tag = etag_of(new_text)
                self._send_bytes(200, new_text.encode("utf-8"), "application/json; charset=utf-8", {"ETag": new_tag})
            except Exception as exc:
                self._send_json(400, {"error": str(exc)})
            return
        self._send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        parts = [seg for seg in parsed.path.split("/") if seg]

        # Create a new process workspace right from the browser!
        if parsed.path == "/api/boards":
            try:
                body = json.loads(self._read_body().decode("utf-8") or "{}")
                folder = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(body.get("folder") or body.get("title") or "New_Process")).strip("_")
                if not folder:
                    raise MinichemeError("Process folder name is required.")
                target_dir = self.server.root_dir / folder
                pfile = target_dir / PROCESS_FILENAME
                if pfile.exists():
                    raise MinichemeError(f"Process '{folder}' already exists.")
                board = new_process(
                    title=str(body.get("title") or folder.replace("_", " ")),
                    description=str(body.get("description") or ""),
                    yolo_all=bool(body.get("yolo")),
                )
                (target_dir / "references").mkdir(parents=True, exist_ok=True)
                write_atomic(pfile, dumps(board))
                slug = self.server.register_board(pfile)
                self._send_json(201, {"slug": slug, "title": board["title"], "path": str(pfile)})
            except Exception as exc:
                self._send_json(400, {"error": str(exc)})
            return

        # Fetch compound properties right from the browser Substances tab!
        if len(parts) == 3 and parts[1] == "api" and parts[2] == "props":
            slug = parts[0]
            bpath = self.server.boards.get(slug)
            if bpath is None:
                self._send_json(404, {"error": f"Unknown board '{slug}'"})
                return
            try:
                body = json.loads(self._read_body().decode("utf-8") or "{}")
                names = [str(x).strip() for x in (body.get("compounds") or []) if str(x).strip()]
                if not names:
                    raise MinichemeError("Provide at least one compound name.")
                fetched = fetch_substances(names)
                append = bool(body.get("append", True))

                def _upd(b: dict[str, Any]):
                    if append:
                        ex = {c["common_name"].lower(): c for c in b.get("substances", [])}
                        for c in fetched:
                            ex[c["common_name"].lower()] = c
                        b["substances"] = list(ex.values())
                    else:
                        b["substances"] = fetched

                board, _ = mutate_process(bpath, _upd)
                text = dumps(board)
                self._send_bytes(200, text.encode("utf-8"), "application/json; charset=utf-8", {"ETag": etag_of(text)})
            except Exception as exc:
                self._send_json(400, {"error": str(exc)})
            return

        self._send_json(404, {"error": "Not found"})


def _pick_free_port(host: str, preferred: int) -> int:
    for port in range(preferred, preferred + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    raise MinichemeError(f"No free port in range {preferred}-{preferred + 19}")


def cmd_serve(args: argparse.Namespace) -> None:
    initial: list[Path] = []
    if args.target:
        p = resolve_process_path(args.target, must_exist=True)
        initial.append(p)
    for discovered in discover_processes(REPO_ROOT):
        if discovered not in initial:
            initial.append(discovered)

    port = _pick_free_port(args.host, args.port)
    srv = MinichemeServer((args.host, port), REPO_ROOT, initial)
    first_slug = srv.register_board(initial[0]) if initial else ""
    url = f"http://{args.host}:{port}/{first_slug}/" if first_slug else f"http://{args.host}:{port}/"
    print(f"Minicheme live board running at {url}")
    if len(initial) > 1:
        print(f"Loaded {len(initial)} processes (switch from header menu).")
    print("Press Ctrl+C to stop.")
    if not args.no_open:
        threading.Timer(0.35, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped Minicheme server.")
    finally:
        srv.server_close()


# ---------------------------------------------------------------------------
# Argument Parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="minicheme",
        description="Minicheme — Conceptual Chemical Process Planning CLI & Live HTML Board",
    )
    p.add_argument("--version", action="version", version=f"minicheme {VERSION}")
    sub = p.add_subparsers(dest="cmd", required=True)

    # init
    sp = sub.add_parser("init", help="Create a new process workspace with Douglas template process.json")
    sp.add_argument("dir", help="Target directory for the new process workspace")
    sp.add_argument("--title", help="Process title")
    sp.add_argument("--desc", help="Process description")
    sp.add_argument("--from-md", help="Read initial description from a Markdown file")
    sp.add_argument("--yolo", action="store_true", help="Enable YOLO up to SM-01 for autonomous end-to-end conceptual planning")
    sp.add_argument("--force", action="store_true", help="Overwrite existing process.json")
    sp.set_defaults(func=cmd_init)

    # next (agent primary command)
    sp = sub.add_parser("next", help="Token-optimized briefing: next ready block + upstream decisions + relevant heuristics")
    sp.add_argument("-p", "--process", help="Path to process folder or process.json")
    sp.set_defaults(func=cmd_next)

    # status
    sp = sub.add_parser("status", help="Compact board overview by state")
    sp.add_argument("-p", "--process", help="Path to process folder or process.json")
    sp.set_defaults(func=cmd_status)

    # show
    sp = sub.add_parser("show", help="Show full details of a block")
    sp.add_argument("id", help="Block ID (e.g. RX-01)")
    sp.add_argument("-p", "--process", help="Path to process folder or process.json")
    sp.set_defaults(func=cmd_show)

    # heuristics
    sp = sub.add_parser("heuristics", help="Compact query of resources/heuristics/heuristics.json")
    sp.add_argument("ids", nargs="*", help="Specific heuristic IDs (e.g. REACT-004 DIST-002)")
    sp.add_argument("--family", help="Filter by family name or key")
    sp.add_argument("--search", help="Keyword search across rules and tags")
    sp.add_argument("--block", help="Show recommended heuristics for a block ID")
    sp.add_argument("--families", action="store_true", help="List all 13 heuristic families and IDs")
    sp.add_argument("--limit", type=int, default=10, help="Max results (default 10)")
    sp.add_argument("--json", action="store_true", help="Output raw JSON")
    sp.add_argument("-p", "--process", help="Path to process folder or process.json (with --block)")
    sp.set_defaults(func=cmd_heuristics)

    # props
    sp = sub.add_parser("props", help="Fetch pure-component properties (chemicals + PubChem) into process.json")
    sp.add_argument("compounds", nargs="+", help="3-5 key compound names (optional Name:Role syntax)")
    sp.add_argument("--roles", help="Comma-separated roles matching compounds")
    sp.add_argument("--azeotropes", help="Azeotrope or phase-behavior note")
    sp.add_argument("--thermo", help="Recommended thermodynamic model (e.g. NRTL-RK)")
    sp.add_argument("--append", action="store_true", help="Merge into existing substances instead of replacing")
    sp.add_argument("-p", "--process", help="Path to process folder or process.json")
    sp.set_defaults(func=cmd_props)

    # basis
    sp = sub.add_parser("basis", help="Update Basis of Design fields in process.json")
    sp.add_argument("--title")
    sp.add_argument("--desc")
    sp.add_argument("--target")
    sp.add_argument("--feedstocks")
    sp.add_argument("--capacity")
    sp.add_argument("--hours", type=int)
    sp.add_argument("--mode")
    sp.add_argument("--spec")
    sp.add_argument("--thermo")
    sp.add_argument("--battery-limits")
    sp.add_argument("--constraints")
    sp.add_argument("--azeotropes")
    sp.add_argument("-p", "--process", help="Path to process folder or process.json")
    sp.set_defaults(func=cmd_basis)

    # start
    sp = sub.add_parser("start", help="Start a ready block (todo -> doing)")
    sp.add_argument("id", help="Block ID")
    sp.add_argument("-m", "--message", help="Brief execution plan note")
    sp.add_argument("--stdin", action="store_true")
    sp.add_argument("--file")
    sp.add_argument("--as", dest="agent", help="Agent name")
    sp.add_argument("-p", "--process")
    sp.set_defaults(func=cmd_start)

    # ask
    sp = sub.add_parser("ask", help="Flag [INFORMATION REQUIRED] and pause for human reply")
    sp.add_argument("id", help="Block ID")
    sp.add_argument("question", nargs="?", default="", help="Question for the human engineer")
    sp.add_argument("--missing", help="Missing engineering parameter")
    sp.add_argument("--why", help="Why this parameter is needed")
    sp.add_argument("--baseline", help="Recommended literature baseline")
    sp.add_argument("--stdin", action="store_true")
    sp.add_argument("--file")
    sp.add_argument("--as", dest="agent")
    sp.add_argument("-p", "--process")
    sp.set_defaults(func=cmd_ask)

    # answer
    sp = sub.add_parser("answer", help="Record human answer to an open question")
    sp.add_argument("id", help="Block ID")
    sp.add_argument("text", nargs="?", default="")
    sp.add_argument("--stdin", action="store_true")
    sp.add_argument("--file")
    sp.add_argument("--as", dest="agent")
    sp.add_argument("-p", "--process")
    sp.set_defaults(func=cmd_answer)

    # note
    sp = sub.add_parser("note", help="Append a note to a block")
    sp.add_argument("id", help="Block ID")
    sp.add_argument("text", nargs="?", default="")
    sp.add_argument("--stdin", action="store_true")
    sp.add_argument("--file")
    sp.add_argument("--as", dest="agent")
    sp.add_argument("-p", "--process")
    sp.set_defaults(func=cmd_note)

    # pause
    sp = sub.add_parser("pause", help="Move a doing block back to todo")
    sp.add_argument("id", help="Block ID")
    sp.add_argument("-m", "--message")
    sp.add_argument("--stdin", action="store_true")
    sp.add_argument("--file")
    sp.add_argument("--as", dest="agent")
    sp.add_argument("-p", "--process")
    sp.set_defaults(func=cmd_pause)

    # finish
    sp = sub.add_parser("finish", help="Submit validated conceptual result (doing -> review, or done under YOLO)")
    sp.add_argument("id", help="Block ID")
    sp.add_argument("-m", "--message", help="Short review summary")
    sp.add_argument("--proposal", help="Conceptual design proposal (Markdown)")
    sp.add_argument("--rationale", help="First-principles shortcut rationale (Markdown)")
    sp.add_argument("--param", action="append", help="Key parameter 'Name|Value|Unit|Note' (repeatable)")
    sp.add_argument("--heuristic", action="append", help="Verified heuristic 'ID:how applied' (repeatable)")
    sp.add_argument("--mermaid", help="Optional Mermaid diagram source")
    sp.add_argument("--stdin", action="store_true", help="Read JSON payload from stdin")
    sp.add_argument("--json-file", help="Read JSON payload from file")
    sp.add_argument("--as", dest="agent")
    sp.add_argument("-p", "--process")
    sp.set_defaults(func=cmd_finish)

    # accept (human helper)
    sp = sub.add_parser("accept", help="Human action: approve proposal, mark block done, or send back")
    sp.add_argument("id", help="Block ID")
    sp.add_argument("--send-back", help="Send block back to todo with feedback")
    sp.add_argument("--note", help="Optional acceptance note")
    sp.add_argument("-p", "--process")
    sp.set_defaults(func=cmd_accept)

    # yolo (human helper)
    sp = sub.add_parser("yolo", help="Human action: enable/disable YOLO autonomous chain up to a block")
    sp.add_argument("id", help="Target block ID")
    sp.add_argument("--before", action="store_true", help="Stop before this block instead of including it")
    sp.add_argument("--off", action="store_true", help="Turn YOLO off on this block")
    sp.add_argument("-p", "--process")
    sp.set_defaults(func=cmd_yolo)

    # propose
    sp = sub.add_parser("propose", help="Propose an additional custom block in a stage")
    sp.add_argument("stage", help="Stage ID (BP, RX, SP, HX, SM)")
    sp.add_argument("title", help="Block title")
    sp.add_argument("objective", nargs="?", default="", help="Engineering objective")
    sp.add_argument("--deps", nargs="*", help="Upstream dependency block IDs")
    sp.add_argument("--heuristics", nargs="*", help="Recommended heuristic IDs")
    sp.add_argument("--as", dest="agent")
    sp.add_argument("-p", "--process")
    sp.set_defaults(func=cmd_propose)

    # depend
    sp = sub.add_parser("depend", help="Add dependency edges (rejects cycles)")
    sp.add_argument("id", help="Downstream block ID")
    sp.add_argument("on", nargs="+", help="Upstream block ID(s)")
    sp.add_argument("-p", "--process")
    sp.set_defaults(func=cmd_depend)

    # check
    sp = sub.add_parser("check", help="Validate process.json schema, DAG, and heuristic citations")
    sp.add_argument("-p", "--process")
    sp.set_defaults(func=cmd_check)

    # export
    sp = sub.add_parser("export", help="Export standalone HTML snapshot or Markdown Process Summary")
    sp.add_argument("out", nargs="?", help="Output file path")
    sp.add_argument("--md", action="store_true", help="Export Markdown brief instead of HTML snapshot")
    sp.add_argument("-p", "--process")
    sp.set_defaults(func=cmd_export)

    # migrate
    sp = sub.add_parser("migrate", help="Migrate a legacy Obsidian Minicheme folder to process.json")
    sp.add_argument("dir", help="Legacy process folder containing 1.1..3.2 notes & .canvas")
    sp.add_argument("--out", help="Output process.json path (default: <dir>/process.json)")
    sp.set_defaults(func=cmd_migrate)

    # serve
    sp = sub.add_parser("serve", help="Launch live interactive HTML board in the browser")
    sp.add_argument("target", nargs="?", help="Optional process folder or process.json to open first")
    sp.add_argument("--port", type=int, default=DEFAULT_PORT)
    sp.add_argument("--host", default="127.0.0.1")
    sp.add_argument("--no-open", action="store_true", help="Do not auto-open browser")
    sp.set_defaults(func=cmd_serve)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
        return 0
    except MinichemeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
