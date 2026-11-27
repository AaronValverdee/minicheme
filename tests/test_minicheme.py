"""Automated test suite for Minicheme 2.0 CLI, workflow rules, heuristics engine, JS parity, and HTTP server."""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
import minicheme  # noqa: E402


def run_cli(*argv: str, stdin_text: str | None = None) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    old_stdin = sys.stdin
    try:
        if stdin_text is not None:
            sys.stdin = io.StringIO(stdin_text)
        with redirect_stdout(out), redirect_stderr(err):
            code = minicheme.main(list(argv))
    finally:
        sys.stdin = old_stdin
    return code, out.getvalue(), err.getvalue()


class TestMinichemeWorkflow(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="minicheme_test_"))
        self.proc_dir = self.tmp / "Demo_Process"
        code, _, err = run_cli("init", str(self.proc_dir), "--title", "Demo MTBE", "--desc", "Produce 10,000 t/yr MTBE")
        self.assertEqual(code, 0, err)
        self.pfile = self.proc_dir / "process.json"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_init_and_compact_next(self):
        code, out, err = run_cli("next", "-p", str(self.proc_dir))
        self.assertEqual(code, 0, err)
        self.assertIn("NEXT BLOCK: BP-01", out)
        self.assertIn("PROC-002", out)
        # Token optimization check: compact briefing stays well under 3,500 chars (~800 tokens)
        self.assertLess(len(out), 3500)

    def test_douglas_hierarchy_gating_and_cycles(self):
        # Cannot start SP-01 while upstream blocks are unfinished
        code, _, err = run_cli("start", "SP-01", "-p", str(self.proc_dir))
        self.assertNotEqual(code, 0)
        self.assertIn("blocked by unfinished dependency", err)

        # Reject cycle BP-01 -> RX-01
        code, _, err = run_cli("depend", "BP-01", "RX-01", "-p", str(self.proc_dir))
        self.assertNotEqual(code, 0)
        self.assertIn("cycle", err.lower())

    def test_heuristics_search_and_validation(self):
        code, out, err = run_cli("heuristics", "--search", "reflux", "--limit", "4")
        self.assertEqual(code, 0, err)
        self.assertIn("DIST-004", out)

        # Advance to RX-01 using YOLO to test RX-01 strict heuristic validation
        run_cli("yolo", "RX-01", "-p", str(self.proc_dir))
        for bid in ("BP-01", "BP-02"):
            self.assertEqual(run_cli("start", bid, "-p", str(self.proc_dir))[0], 0)
            payload = json.dumps({"proposal": f"Solved {bid}", "rationale": "First principles.", "heuristics": [{"id": "PROC-002", "applied": "Continuous"}]})
            self.assertEqual(run_cli("finish", bid, "-p", str(self.proc_dir), "--stdin", stdin_text=payload)[0], 0)

        self.assertEqual(run_cli("start", "RX-01", "-p", str(self.proc_dir))[0], 0)
        # Missing heuristic on RX-01 must fail
        bad_no_h = json.dumps({"proposal": "Exothermic", "rationale": "ΔH = -37 kJ/mol"})
        code, _, err = run_cli("finish", "RX-01", "-p", str(self.proc_dir), "--stdin", stdin_text=bad_no_h)
        self.assertNotEqual(code, 0)
        self.assertIn("heuristic", err.lower())

        # Hallucinated heuristic ID must fail
        bad_id = json.dumps({"proposal": "Exothermic", "rationale": "ΔH = -37 kJ/mol", "heuristics": [{"id": "REACT-999", "applied": "Fake"}]})
        code, _, err = run_cli("finish", "RX-01", "-p", str(self.proc_dir), "--stdin", stdin_text=bad_id)
        self.assertNotEqual(code, 0)
        self.assertIn("Unknown heuristic ID", err)

        # Valid heuristic auto-hydrates summary & source and moves RX-01 (YOLO target) to review
        good = json.dumps({
            "proposal": "Moderately exothermic liquid-phase synthesis.",
            "rationale": "ΔT_ad = 42.4 °C with C4 diluent heat sink.",
            "parameters": [{"name": "ΔT_ad", "value": "42.4", "unit": "°C", "note": "C4 inerts"}],
            "heuristics": [{"id": "REACT-004", "applied": "C4 inerts absorb reaction heat."}],
            "summary": "Confirmed moderate exotherm.",
        })
        code, out, err = run_cli("finish", "RX-01", "-p", str(self.proc_dir), "--stdin", stdin_text=good)
        self.assertEqual(code, 0, err)
        self.assertIn("-> review", out)

        board = minicheme.load_process(self.pfile)
        rx1 = minicheme.block_map(board)["RX-01"]
        self.assertEqual(rx1["state"], "review")
        self.assertTrue(rx1["heuristics"][0]["source"])
        self.assertTrue(rx1["heuristics"][0]["summary"])

    def test_ask_answer_and_sendback_loop(self):
        self.assertEqual(run_cli("start", "BP-01", "-p", str(self.proc_dir))[0], 0)
        code, _, err = run_cli(
            "ask", "BP-01", "What purity spec is required?",
            "--missing", "Product purity",
            "--why", "Sets column stages",
            "--baseline", "99.9 wt%",
            "-p", str(self.proc_dir),
        )
        self.assertEqual(code, 0, err)

        # `next` must stop and surface the question
        code, out, _ = run_cli("next", "-p", str(self.proc_dir))
        self.assertEqual(code, 0)
        self.assertIn("STOP — Waiting for human answer", out)

        # Cannot finish while question is unanswered
        payload = json.dumps({"proposal": "Continuous 10,000 t/yr"})
        code, _, err = run_cli("finish", "BP-01", "-p", str(self.proc_dir), "--stdin", stdin_text=payload)
        self.assertNotEqual(code, 0)
        self.assertIn("unanswered question", err)

        # Answer clears waiting state -> finish succeeds -> review
        self.assertEqual(run_cli("answer", "BP-01", "Use 99.9 wt% MTBE.", "-p", str(self.proc_dir))[0], 0)
        code, out, err = run_cli("finish", "BP-01", "-p", str(self.proc_dir), "--stdin", stdin_text=payload)
        self.assertEqual(code, 0, err)
        self.assertIn("-> review", out)

        # Human sends back with feedback -> `next` surfaces feedback
        self.assertEqual(run_cli("accept", "BP-01", "--send-back", "Add 50% turndown constraint", "-p", str(self.proc_dir))[0], 0)
        code, out, _ = run_cli("next", "-p", str(self.proc_dir))
        self.assertIn("REVIEW FEEDBACK TO ADDRESS", out)
        self.assertIn("50% turndown", out)

    def test_props_and_exports(self):
        code, out, err = run_cli(
            "props", "Isobutylene:Reactant", "Methanol:Feed", "MTBE:Product",
            "--thermo", "NRTL-RK",
            "-p", str(self.proc_dir),
        )
        self.assertEqual(code, 0, err)
        self.assertIn("Updated 3 substances", out)

        # Export HTML snapshot & Markdown brief
        snap = self.tmp / "snap.html"
        md = self.tmp / "brief.md"
        self.assertEqual(run_cli("export", str(snap), "-p", str(self.proc_dir))[0], 0)
        self.assertEqual(run_cli("export", str(md), "--md", "-p", str(self.proc_dir))[0], 0)
        html_txt = snap.read_text(encoding="utf-8")
        self.assertIn("Demo MTBE", html_txt)
        self.assertNotIn('<script id="minicheme-snapshot" type="application/json"></script>', html_txt)
        self.assertIn("NRTL-RK", md.read_text(encoding="utf-8"))

    def test_example1_is_valid_and_js_serializer_matches_python(self):
        ex1 = REPO_ROOT / "Example1" / "process.json"
        code, out, err = run_cli("check", "-p", str(ex1))
        self.assertEqual(code, 0, err)
        self.assertIn("0 errors", out)

        if not shutil.which("node"):
            self.skipTest("node not installed")

        html_text = (REPO_ROOT / "minicheme.html").read_text(encoding="utf-8")
        # Extract pure canonical/serialize section from minicheme.html and run under Node
        start = html_text.index("const VALID_STATES =")
        end = html_text.index("function blockMap(board)")
        js_core = html_text[start:end]
        board_json = ex1.read_text(encoding="utf-8")
        script = (
            js_core
            + "\nconst fs = require('fs');\n"
            + f"const b = JSON.parse(fs.readFileSync({json.dumps(str(ex1))}, 'utf8'));\n"
            + "process.stdout.write(serializeBoard(b));\n"
        )
        res = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True, encoding="utf-8")
        py_out = minicheme.dumps(minicheme.load_process(ex1))
        self.assertEqual(res.stdout, py_out)


class TestMinichemeServer(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="minicheme_srv_"))
        self.pdir = self.tmp / "Alpha_Process"
        run_cli("init", str(self.pdir), "--title", "Alpha Plant")
        self.pfile = self.pdir / "process.json"
        self.server = minicheme.MinichemeServer(("127.0.0.1", 0), self.tmp, [self.pfile])
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _get(self, path: str, headers: dict[str, str] | None = None):
        req = urllib.request.Request(self.base + path, headers=headers or {})
        return urllib.request.urlopen(req, timeout=5)

    def test_server_endpoints_and_cas(self):
        with self._get("/api/health") as r:
            self.assertEqual(r.status, 200)
            self.assertTrue(json.loads(r.read())["ok"])

        with self._get("/api/boards") as r:
            boards = json.loads(r.read())["boards"]
            self.assertEqual(len(boards), 1)
            slug = boards[0]["slug"]

        # GET /<slug>/ serves minicheme.html (200 OK, no redirect loop)
        with self._get(f"/{slug}/") as r:
            self.assertEqual(r.status, 200)
            self.assertIn(b"Minicheme", r.read())

        with self._get("/api/heuristics") as r:
            hdata = json.loads(r.read())
            self.assertEqual(len(hdata["families"]), 13)

        # GET board + ETag + 304 Not Modified
        with self._get(f"/{slug}/api/board") as r:
            etag = r.headers["ETag"]
            board = json.loads(r.read())
            self.assertEqual(board["title"], "Alpha Plant")

        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._get(f"/{slug}/api/board", headers={"If-None-Match": etag})
        self.assertEqual(ctx.exception.code, 304)

        # PUT with matching ETag succeeds
        board["title"] = "Alpha Plant v2"
        req = urllib.request.Request(
            f"{self.base}/{slug}/api/board",
            data=json.dumps(board).encode("utf-8"),
            method="PUT",
            headers={"Content-Type": "application/json", "If-Match": etag},
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            self.assertEqual(r.status, 200)
            new_etag = r.headers["ETag"]
            self.assertNotEqual(new_etag, etag)

        # PUT with stale ETag returns 409 Conflict
        req_stale = urllib.request.Request(
            f"{self.base}/{slug}/api/board",
            data=json.dumps(board).encode("utf-8"),
            method="PUT",
            headers={"Content-Type": "application/json", "If-Match": etag},
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req_stale, timeout=5)
        self.assertEqual(ctx.exception.code, 409)

        # POST /api/boards creates a new workspace
        req_new = urllib.request.Request(
            f"{self.base}/api/boards",
            data=json.dumps({"title": "Beta Synthesis", "folder": "Beta_Process"}).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req_new, timeout=5) as r:
            self.assertEqual(r.status, 201)
            created = json.loads(r.read())
            self.assertEqual(created["title"], "Beta Synthesis")

        # Export endpoints return HTML and Markdown
        with self._get(f"/{slug}/api/export/html") as r:
            self.assertIn(b"Alpha Plant v2", r.read())
        with self._get(f"/{slug}/api/export/md") as r:
            self.assertIn(b"Alpha Plant v2", r.read())


if __name__ == "__main__":
    unittest.main()
