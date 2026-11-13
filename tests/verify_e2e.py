#!/usr/bin/env python3
"""End-to-end API + Headless Chromium CDP interactive browser verification across all 6 S7 MedPrep views."""
from __future__ import annotations

import asyncio
import base64
import json
import sqlite3
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parent.parent
BASE = "http://127.0.0.1:8011"
SHOT_DIR = ROOT / "tests" / "screenshots"


def get(path: str):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=15) as r:
        return r.status, r.headers.get("Content-Type", ""), r.read()


def post_json(path: str, payload: dict):
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status, json.loads(r.read().decode())


async def cdp_verify() -> None:
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as user_data:
        chrome = subprocess.Popen(
            [
                "/usr/bin/google-chrome",
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                "--window-size=1440,1000",
                f"--user-data-dir={user_data}",
                "--remote-debugging-port=9235",
                f"{BASE}/",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            ws_url = None
            for _ in range(40):
                try:
                    tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9235/json/list", timeout=3).read().decode())
                    page_tabs = [t for t in tabs if t.get("type") == "page"]
                    if page_tabs:
                        ws_url = page_tabs[0]["webSocketDebuggerUrl"]
                        break
                except Exception:
                    await asyncio.sleep(0.3)
            assert ws_url, "Chromium CDP failed to expose target"

            async with websockets.connect(ws_url, max_size=20 * 1024 * 1024) as ws:
                msg_id = 0
                errors: list[str] = []

                async def call(method: str, params: dict | None = None):
                    nonlocal msg_id
                    msg_id += 1
                    cid = msg_id
                    await ws.send(json.dumps({"id": cid, "method": method, "params": params or {}}))
                    while True:
                        raw = json.loads(await ws.recv())
                        if raw.get("method") == "Runtime.exceptionThrown":
                            errors.append(json.dumps(raw.get("params")))
                        elif raw.get("method") == "Network.responseReceived":
                            st = raw.get("params", {}).get("response", {}).get("status", 200)
                            url = raw.get("params", {}).get("response", {}).get("url", "")
                            if st >= 400:
                                errors.append(f"HTTP {st} on {url}")
                        if raw.get("id") == cid:
                            return raw.get("result", {})

                async def eval_js(expr: str):
                    res = await call("Runtime.evaluate", {"expression": expr, "awaitPromise": True, "returnByValue": True})
                    return res.get("result", {}).get("value")

                async def click_text(substr: str):
                    ok = await eval_js(
                        f"""(() => {{
                            const els = Array.from(document.querySelectorAll('button, a, label'));
                            const t = els.find(e => e.textContent && e.textContent.includes({json.dumps(substr)}));
                            if (!t) return false;
                            t.click();
                            return true;
                        }})()"""
                    )
                    assert ok, f"Element containing '{substr}' not found"
                    await asyncio.sleep(0.7)

                async def save_shot(name: str):
                    res = await call("Page.captureScreenshot", {"format": "png", "fromSurface": True})
                    (SHOT_DIR / name).write_bytes(base64.b64decode(res["data"]))

                await call("Runtime.enable")
                await call("Network.enable")
                await call("Page.enable")
                await asyncio.sleep(1.5)

                # 1. Dashboard
                txt = await eval_js("document.body.innerText")
                assert "septième session" in txt, "Dashboard missing heading"
                await save_shot("01_dashboard.png")

                # 2. Courses & Visual Sheet
                await click_text("Cours & Fiches")
                await asyncio.sleep(0.8)
                await click_text("Maladie de Behçet")
                await asyncio.sleep(0.6)
                await click_text("Feuilleter ici")
                for _ in range(25):
                    has_img = await eval_js("(() => { const el = document.querySelector('img[alt^=\"Page 1\"]'); return Boolean(el && el.complete && el.naturalWidth > 0); })()")
                    if has_img:
                        break
                    await asyncio.sleep(0.3)
                assert has_img, "Behcet PDF visual sheet failed to render"
                await save_shot("02_courses_visual.png")

                # 3. Clinical Situations
                await click_text("Clinique")
                await asyncio.sleep(0.6)
                await click_text("Prendre en charge")
                await asyncio.sleep(0.5)
                await click_text("Artère cérébrale antérieure")
                await click_text("Valider cette conduite clinique")
                await asyncio.sleep(0.5)
                txt3 = await eval_js("document.body.innerText")
                assert "perle clinique" in txt3.lower(), f"Missing Perle Clinique in: {txt3[:400]}"
                await save_shot("03_clinical_sim.png")

                # 4. Exam Simulator (APS 2025 SN + Scan Peek)
                await click_text("Examens")
                await asyncio.sleep(0.6)
                await click_text("APS 2025 (30 Q)")
                await asyncio.sleep(0.8)
                await click_text("Voir scan original")
                for _ in range(20):
                    has_scan = await eval_js("(() => { const el = document.querySelector('img[alt=\"Scan examen original\"]'); return Boolean(el && el.complete && el.naturalWidth > 0); })()")
                    if has_scan:
                        break
                    await asyncio.sleep(0.25)
                assert has_scan, "Scan image peek did not load"
                await save_shot("04_exam_aps_scan.png")

                # 5. Strike Radar
                await click_text("Radar")
                await asyncio.sleep(0.8)
                txt5 = await eval_js("document.body.innerText")
                assert "couverture par banque" in txt5.lower()
                await save_shot("05_radar.png")

                # 6. Studio Scans & OCR
                await click_text("Scans")
                for _ in range(20):
                    has_studio_img = await eval_js("(() => { const el = document.querySelector('img[alt^=\"aps-\"]'); return Boolean(el && el.complete && el.naturalWidth > 0); })()")
                    if has_studio_img:
                        break
                    await asyncio.sleep(0.25)
                assert has_studio_img, "Studio original scan PNG did not load"
                await save_shot("06_scan_studio.png")

                # 7. Possible Question (Wa3rin QCM/QROC + Complex Clinical Cases)
                await click_text("Possible Question")
                await asyncio.sleep(0.9)
                txt7 = await eval_js("document.body.innerText")
                assert "questions prédites" in txt7.lower(), f"Possible Question KPI missing in: {txt7[:300]}"
                # Select first option if QCM or type into textarea if QROC, then validate
                answered = await eval_js(
                    """(() => {
                        const ta = document.querySelector('textarea');
                        if (ta) {
                            const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
                            setter.call(ta, 'Biopsie diagnostic seuil positif critere urgence');
                            ta.dispatchEvent(new Event('input', { bubbles: true }));
                            return true;
                        }
                        const opt = Array.from(document.querySelectorAll('button')).find(b => b.querySelector('span.font-mono-tabular')?.textContent?.trim() === 'A');
                        if (opt) { opt.click(); return true; }
                        return false;
                    })()"""
                )
                assert answered, "Could not fill/select answer in Possible Question"
                await asyncio.sleep(0.3)
                await click_text("Valider ma réponse")
                await asyncio.sleep(0.7)
                txt7b = await eval_js("document.body.innerText")
                assert "appui document" in txt7b.lower() or "réponse exacte" in txt7b.lower() or "barème" in txt7b.lower()
                await save_shot("07_possible_questions.png")

                # Switch to Cas Cliniques Complexes & open first complex case
                await click_text("Cas Cliniques Complexes")
                await asyncio.sleep(0.7)
                await click_text("Prendre en charge")
                await asyncio.sleep(0.7)
                txt8 = await eval_js("document.body.innerText")
                assert "éléments séméiologiques" in txt8.lower(), f"Complex clinical case did not open: {txt8[:300]}"
                await save_shot("08_possible_cases.png")

                assert not errors, f"Browser runtime/network errors detected: {errors}"
                print("CDP HEADLESS BROWSER E2E VERIFICATION PASSED: 0 runtime/network errors, 8 screenshots saved.")
        finally:
            chrome.terminate()
            try:
                chrome.wait(timeout=3)
            except Exception:
                chrome.kill()


def main() -> None:
    proc = subprocess.Popen(
        ["python3", "-m", "uvicorn", "backend.app:app", "--host", "127.0.0.1", "--port", "8011"],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        for _ in range(30):
            try:
                st, _, body = get("/api/health")
                if st == 200:
                    print("HEALTH:", body.decode())
                    break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError("FastAPI failed to start")

        dash = json.loads(get("/api/dashboard")[2].decode())
        assert dash["summary"]["total_courses"] >= 113
        assert dash["summary"]["total_questions"] >= 1000
        assert len(dash["modules"]) == 4

        aps_q = json.loads(get("/api/questions?source_label=EXAMEN%20APS%202025%20SN&limit=2")[2].decode())["questions"][0]
        _, r1 = post_json(f"/api/questions/{aps_q['id']}/attempt", {"session_id": "api_chk", "mode": "practice", "selected_answers": aps_q["correct_answers_json"]})
        assert r1["is_correct"] is True

        neu_q = json.loads(get("/api/questions?source_label=EXAMEN%20BLANC%20NEURO%202025%20(Corrig%C3%A9)&limit=2")[2].decode())["questions"][0]
        _, r2 = post_json(f"/api/questions/{neu_q['id']}/attempt", {"session_id": "api_chk", "mode": "practice", "written_answer": "AVC ischemique < 3 mois hemorragique glycemie PA > 185/110 UGD"})
        assert r2["partial_score"] > 0

        poss = json.loads(get("/api/possible-questions?limit=5")[2].decode())
        assert poss["summary"]["total_questions"] >= 150, f"Too few predicted questions: {poss['summary']}"
        assert poss["summary"]["total_cases"] >= 15, f"Too few predicted cases: {poss['summary']}"
        pq0 = poss["questions"][0]
        _, r3 = post_json(
            f"/api/questions/{pq0['id']}/attempt",
            {
                "session_id": "api_chk",
                "mode": pq0["question_type"],
                "selected_answers": pq0["correct_answers_json"] if pq0["question_type"] != "qroc" else [],
                "written_answer": " ".join(pq0.get("rubric_json", {}).get("points", [])) if pq0["question_type"] == "qroc" else "",
            },
        )
        assert r3["is_predicted"] is True

        # Clean up synthetic api_chk attempt so user telemetry starts fresh
        conn = sqlite3.connect(str(ROOT / "data" / "s7_platform.db"))
        conn.execute("DELETE FROM question_attempts WHERE session_id = 'api_chk'")
        conn.commit()
        conn.close()

        print("API & grading verification passed.")
        asyncio.run(cdp_verify())
        conn = sqlite3.connect(str(ROOT / "data" / "s7_platform.db"))
        conn.execute("DELETE FROM question_attempts WHERE session_id = 'possible_question'")
        conn.commit()
        conn.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()
