#!/usr/bin/env python3
"""Parse all text + raster-highlighted Corrigés, Examens Blancs Neuro, Quiz Amphi, and unkeyed QEs."""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.db import DATA_DIR, DB_PATH, get_conn, init_db  # noqa: E402
from pipeline.ingest_inventory import norm  # noqa: E402

CORR_RENDER_DIR = DATA_DIR / "scans" / "corr_pages"

# Text + highlight Corrigés (PDFs with text layer + raster highlights / inline notes)
HIGHLIGHT_CORRIGES = [
    ("bennani_c", "14gHFBdyMUjFohx5O8gJyYaSKyqGfAWn6", "anapath", "Anatomopathologie", "Prof Bennani", "QE PR BENNANI (Corrigé)", "QE"),
    ("karich_c", "1pW2OAQUSwELzpF8EDvfPYzioYhqbTq7S", "anapath", "Anatomopathologie", "Prof Karich", "QE PR KARICH (Corrigé)", "QE"),
    ("latrech_c", "1J_GlnTGXCENHwyCpClJ8ejtrlYqBAiQO", "endocrino-dermato", "Endocrinologie", "Prof Latrech", "QE PR LATRECH (Corrigé)", "QE"),
    ("rouf_c", "1XI8GGNhnNstdg2CWtynGEoZl5v9970yi", "endocrino-dermato", "Endocrinologie", "Prof Rouf", "QE PR ROUF (Corrigé)", "QE"),
    ("ecn_derm1_c", "1QYDwNCCX-hetHgJYwtNq36sh787sVg2g", "endocrino-dermato", "Dermatologie", "Collège ECN", "QE ECN DERMATO P1 (Corrigé)", "QE"),
    ("ecn_derm2_c", "1nfih9QiR1neqeVTPxsvBOl0Y2SC3xsma", "endocrino-dermato", "Dermatologie", "Collège ECN", "QE ECN DERMATO P2 (Corrigé)", "QE"),
    ("alaoui_c", "17DxRxdk15shfDVRPOuyW9BGzY1vazV5A", "hemato-onco", "Hématologie", "Prof Alaoui", "QE PR ALAOUI (Corrigé)", "QE"),
    ("hamaz_c", "1m-npP3Ev3l6v3QSpgJ-WAwcrhGDz7lEn", "hemato-onco", "Hématologie", "Prof Hamaz", "QE PR HAMAZ (Corrigé)", "QE"),
    ("serraj_c", "1Xb5r3TyMBtwi8k0DyB4rm9Q_BMBHDwL7", "hemato-onco", "Hématologie", "Prof Serraj", "QE PR SERRAJ (Corrigé)", "QE"),
    ("onco_c", "1d8aPlpbp-VRfg9z6rrsSUr8ZrVXtokuL", "hemato-onco", "Oncologie", "Prof Mezouar / Afkir", "QE ONCO (Corrigé)", "QE"),
]

UNKEYED_TEXT_QES = [
    ("halaoui_nc", "1RJaOXtl_4Ydc1ogIfpVzKaGwNKOZCVOL", "anapath", "Anatomopathologie", "Prof Halaoui", "QE PR HALAOUI", "QE"),
    ("bouichrat_nc", "12Y_SqtS5Nhp8HHsL3zMKxCi8pORUbM5f", "endocrino-dermato", "Endocrinologie", "Prof Bouichrat", "QE PR BOUICHRAT", "QE"),
]

NS = {"x": "http://www.w3.org/1999/xhtml"}
OPT_LINE_RE = re.compile(r"^([A-J])(?:[\.\)]|\s+(?=[A-ZÀ-ÿa-z]))\s*(.+)$")
GROUP_STMT_RE = re.compile(r"^([a-e])(?:[\.\)])\s*(.+)$")
GROUP_CHOICE_RE = re.compile(r"([A-E])\s*\(\s*([a-e](?:\s*[,;.]\s*[a-e])*)\s*\)")


def find_best_course_id(conn, mod_id: str, title_hint: str) -> int | None:
    rows = conn.execute("SELECT id, canonical_title, professor FROM courses WHERE module_id = ?", (mod_id,)).fetchall()
    from pipeline.ingest_inventory import token_score
    best_id, best_sc = None, 0.0
    for r in rows:
        sc = token_score(r["canonical_title"], title_hint, r["professor"], None)
        if sc > best_sc:
            best_sc, best_id = sc, r["id"]
    return best_id if best_sc >= 0.32 else None


def is_bold_or_heading(text: str) -> bool:
    t = text.strip()
    if len(t) < 4:
        return False
    low = t.lower()
    if t.endswith(":") and not OPT_LINE_RE.match(t) and not GROUP_STMT_RE.match(t):
        return True
    if any(low.startswith(p) for p in ("cas clinique", "exercice", "question", "concernant", "parmi", "quel", "quelle", "quelles", "quels", "devant", "indiquez", "dans l", "au cours")):
        return True
    return False


def render_pages_cached(pdf_path: Path, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(out_dir.glob("page-*.png"))
    if existing:
        return existing
    subprocess.run(["pdftoppm", "-png", "-r", "105", str(pdf_path), str(out_dir / "page")], check=True, capture_output=True)
    return sorted(out_dir.glob("page-*.png"))


def parse_highlight_pdf(conn, slug: str, file_id: str, mod_id: str, sub: str, prof: str, label: str, sess: str) -> int:
    row = conn.execute("SELECT local_path FROM drive_files WHERE id = ?", (file_id,)).fetchone()
    if not row or not row["local_path"]:
        print(f"SKIP {slug}: not cached")
        return 0
    pdf_path = DATA_DIR / row["local_path"]
    render_dir = CORR_RENDER_DIR / slug
    pngs = render_pages_cached(pdf_path, render_dir)

    xml_raw = subprocess.check_output(["pdftotext", "-bbox-layout", str(pdf_path), "-"]).decode("utf-8", errors="ignore")
    root = ET.fromstring(xml_raw)
    pages_xml = root.findall(".//x:page", NS)

    inserted = 0
    q_counter = 0
    current_topic = sub
    current_vignette = None

    cur_q: dict[str, Any] | None = None

    def flush_q(item: dict[str, Any] | None) -> None:
        nonlocal inserted, q_counter
        if not item:
            return
        opts = item["options"]
        stmts = item["statements"]
        if not opts and not stmts:
            return
        q_counter += 1
        qtype = "qcm_group" if stmts and any("(" in o["text"] or re.match(r"^[a-e,\s;]+$", o["text"]) for o in opts) else "qcm_multi"
        corr = item["correct"]
        if qtype == "qcm_group" and not corr and item.get("true_stmts"):
            ts = sorted(set(item["true_stmts"]))
            for o in opts:
                og = sorted(re.findall(r"[a-e]", o["text"]))
                if og == ts:
                    corr = [o["letter"]]
                    break
        corr = sorted(set(corr), key=lambda x: "ABCDEFGHIJ".find(x) if x in "ABCDEFGHIJ" else 99)
        stem = re.sub(r"\s+", " ", " ".join(item["stem_lines"])).strip()
        if not stem:
            stem = current_topic
        if len(stem) < 6:
            return

        cid = find_best_course_id(conn, mod_id, f"{item['topic']} {stem}")
        ext_key = f"{slug}_{q_counter}"
        conn.execute(
            """
            INSERT INTO questions (
                external_key, module_id, sub_discipline, course_id, professor, source_file_id,
                source_label, exam_year, session, question_number, vignette_group_id, vignette_text,
                question_type, stem, statements_json, options_json, correct_answers_json,
                rubric_json, explanation, verification_status, scan_page_image, frequency_tag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(external_key) DO UPDATE SET
                stem=excluded.stem,
                statements_json=excluded.statements_json,
                options_json=excluded.options_json,
                correct_answers_json=excluded.correct_answers_json,
                scan_page_image=excluded.scan_page_image,
                course_id=COALESCE(excluded.course_id, questions.course_id)
            """,
            (
                ext_key, mod_id, sub, cid, prof, file_id,
                label, "2025", sess, q_counter,
                f"{slug}_vig_{item['vig_idx']}" if item.get("vignette") else None,
                item.get("vignette"),
                qtype, stem,
                json.dumps(stmts, ensure_ascii=False),
                json.dumps(opts, ensure_ascii=False),
                json.dumps(corr, ensure_ascii=False),
                "{}",
                f"Thème : {item['topic']}. Clé extraite automatiquement des surlignages vert/jaune du corrigé {label}.",
                "corrigé_raster" if corr else "unverified",
                item.get("page_img"),
                "annale_qe",
            ),
        )
        inserted += 1

    vig_idx = 0
    in_vignette = False
    vig_lines: list[str] = []

    for p_idx, pg_el in enumerate(pages_xml):
        if p_idx >= len(pngs):
            break
        im = np.array(Image.open(pngs[p_idx]).convert("RGB"))
        ih, iw = im.shape[:2]
        pw, ph = float(pg_el.attrib["width"]), float(pg_el.attrib["height"])
        sx, sy = iw / pw, ih / ph
        page_img_url = f"/api/scans/corr_pages/{slug}/{pngs[p_idx].name}"

        for ln in pg_el.findall(".//x:line", NS):
            ws = ln.findall(".//x:word", NS)
            if not ws:
                continue
            text = re.sub(r"\s+", " ", " ".join((w.text or "") for w in ws)).strip()
            if not text or re.fullmatch(r"\d{1,3}", text):
                continue
            # Filter right-hand red/pink reference boxes & handwritten red-pen fragments far right
            x0 = float(ws[0].attrib["xMin"])
            y0 = min(float(w.attrib["yMin"]) for w in ws)
            x1 = max(float(w.attrib["xMax"]) for w in ws)
            y1 = max(float(w.attrib["yMax"]) for w in ws)

            if x0 > pw * 0.60 and len(text) < 55:
                continue  # sidebar summary tables on Benanni/Karich/Latrech/Serraj
            if re.match(r"^(ANATOMIE|PATHOLOGIE|ENDOCRINOLOGIE|DERMATOLOGIE|DETMATOLOGIE|LES URGENCES|CHIRURGIE)\b", text):
                if len(text) < 60:
                    continue

            # Check vignette starter
            if re.match(r"^Cas clinique\s*:", text, re.IGNORECASE):
                flush_q(cur_q)
                cur_q = None
                in_vignette = True
                vig_idx += 1
                vig_lines = [text]
                continue

            # Check group choices line like "A (c,d)," or "A (c,d), B(a,b), C(a,b,c)..."
            gmatches = GROUP_CHOICE_RE.findall(text)
            if len(gmatches) >= 1 and cur_q and cur_q["statements"] and re.match(r"^[A-E]\s*\(", text):
                for L, g in gmatches:
                    if not any(o["letter"] == L for o in cur_q["options"]):
                        cur_q["options"].append({"letter": L, "text": g.replace(" ", "")})
                # Detect highlight box or red circle per group choice word position!
                for word in ws:
                    wt = (word.text or "").strip()
                    gm = re.match(r"^([A-E])(?:\(|$)", wt)
                    if gm and any(o["letter"] == gm.group(1) for o in cur_q["options"]):
                        wx0 = float(word.attrib["xMin"])
                        wx1 = float(word.attrib["xMax"])
                        lx0, lx1 = max(0, int((wx0 - 6) * sx)), min(iw, int((wx1 + 16) * sx))
                        yy0, yy1 = max(0, int((y0 - 4) * sy)), min(ih, int((y1 + 4) * sy))
                        crop = im[yy0:yy1, lx0:lx1].astype(int)
                        if crop.size > 0:
                            gr = np.mean((crop[:, :, 1] - crop[:, :, 0] > 18) & (crop[:, :, 1] > 150))
                            yr = np.mean((np.minimum(crop[:, :, 0], crop[:, :, 1]) - crop[:, :, 2] > 65) & (crop[:, :, 0] > 195))
                            rr = np.mean((crop[:, :, 0] - np.maximum(crop[:, :, 1], crop[:, :, 2]) > 45))
                            if gr > 0.10 or yr > 0.12 or rr > 0.03:
                                cur_q["correct"].append(gm.group(1))
                continue

            # Check proposition lowercase a) b) c) d) e)
            gm = GROUP_STMT_RE.match(text)
            if gm and cur_q is not None and not cur_q["options"]:
                cur_q["statements"].append({"letter": gm.group(1), "text": gm.group(2).strip()})
                cur_q["last_kind"] = "stmt"
                # Track yellow-highlighted statements in Bennani for group matching fallback
                bx0, bx1 = max(0, int(x0 * sx)), min(iw, int(min(x1, x0 + 160) * sx))
                yy0, yy1 = max(0, int((y0 - 2) * sy)), min(ih, int((y1 + 2) * sy))
                scrop = im[yy0:yy1, bx0:bx1].astype(int)
                if scrop.size > 0 and np.mean((np.minimum(scrop[:, :, 0], scrop[:, :, 1]) - scrop[:, :, 2] > 65) & (scrop[:, :, 0] > 195)) > 0.14:
                    cur_q.setdefault("true_stmts", []).append(gm.group(1))
                continue

            # Check option A. B. C. ...
            om = OPT_LINE_RE.match(text)
            if om and x0 < 120:
                letter = om.group(1)
                opt_text = om.group(2).strip()
                if cur_q is None:
                    # Orphan option line
                    continue
                if cur_q.get("options") and letter == "A" and len(cur_q["options"]) >= 2:
                    # Unexpected new option A without explicit stem
                    flush_q(cur_q)
                    cur_q = None
                    continue
                in_vignette = False
                if vig_lines:
                    current_vignette = " ".join(vig_lines)
                    vig_lines = []
                cur_q["options"].append({"letter": letter, "text": opt_text})
                cur_q["last_kind"] = "opt"

                # Pixel highlight check on this exact page
                lx0, lx1 = max(0, int((x0 - 4) * sx)), min(iw, int((x0 + 18) * sx))
                bx0, bx1 = max(0, int(x0 * sx)), min(iw, int(min(x1, x0 + 150) * sx))
                mx0, mx1 = max(0, int((x0 - 18) * sx)), max(0, int((x0 - 2) * sx))
                yy0, yy1 = max(0, int((y0 - 2) * sy)), min(ih, int((y1 + 2) * sy))
                lcrop = im[yy0:yy1, lx0:lx1].astype(int)
                bcrop = im[yy0:yy1, bx0:bx1].astype(int)
                mcrop = im[yy0:yy1, mx0:mx1].astype(int) if mx1 > mx0 else lcrop[:, :1]

                gr = np.mean((lcrop[:, :, 1] - lcrop[:, :, 0] > 18) & (lcrop[:, :, 1] > 150)) if lcrop.size else 0
                yr = np.mean((np.minimum(bcrop[:, :, 0], bcrop[:, :, 1]) - bcrop[:, :, 2] > 65) & (bcrop[:, :, 0] > 195)) if bcrop.size else 0
                rx = np.mean((mcrop[:, :, 0] - np.maximum(mcrop[:, :, 1], mcrop[:, :, 2]) > 45)) if mcrop.size else 0
                if (gr > 0.12 or yr > 0.14) and rx < 0.18:
                    cur_q["correct"].append(letter)
                elif gr > 0.25 or yr > 0.35:
                    cur_q["correct"].append(letter)
                continue

            # Continuation line vs new question stem vs topic header
            if cur_q and cur_q["options"] and x0 > 80 and not is_bold_or_heading(text):
                # Multi-line option continuation
                cur_q["options"][-1]["text"] += " " + text
                continue
            if cur_q and cur_q["statements"] and not cur_q["options"] and x0 > 80 and not is_bold_or_heading(text):
                cur_q["statements"][-1]["text"] += " " + text
                continue

            # Check if this is a green explanation note at bottom of a vignette question
            if cur_q and cur_q["options"] and (text.lower().startswith("la patiente") or text.lower().startswith("nb ") or text.lower().startswith("rappel")):
                continue

            # Check if previous question had options already -> new topic or new stem!
            if cur_q and (cur_q["options"] or cur_q["statements"]):
                flush_q(cur_q)
                cur_q = None
                in_vignette = False

            # Check short colored section header (topic)
            bx0, bx1 = max(0, int(x0 * sx)), min(iw, int(min(x1, x0 + 120) * sx))
            yy0, yy1 = max(0, int(y0 * sy)), min(ih, int(y1 * sy))
            hcrop = im[yy0:yy1, bx0:bx1].astype(int)
            is_blue_header = hcrop.size > 0 and np.mean((hcrop[:, :, 2] - hcrop[:, :, 0] > 40) & (hcrop[:, :, 2] > 170)) > 0.15
            if (is_blue_header or (len(text) < 48 and text.endswith(":") and not text.lower().startswith(("parmi", "quel", "quelle", "concernant", "devant", "dans", "lesquels", "lesquelles")))) and "cas clinique" not in text.lower():
                current_topic = text.rstrip(":").strip()
                current_vignette = None
                vig_lines = []
                in_vignette = False
                continue

            if in_vignette and not text.rstrip().endswith("?") and not any(text.lower().startswith(k) for k in ("quel", "quelle", "quelles", "quels", "parmi", "indiquez")):
                vig_lines.append(text)
                continue
            if in_vignette and (text.rstrip().endswith("?") or any(text.lower().startswith(k) for k in ("quel", "quelle", "quelles", "quels"))):
                in_vignette = False
                current_vignette = " ".join(vig_lines).strip()
                vig_lines = []

            if cur_q is None:
                cur_q = {
                    "topic": current_topic,
                    "vignette": current_vignette,
                    "vig_idx": vig_idx,
                    "stem_lines": [text],
                    "statements": [],
                    "options": [],
                    "correct": [],
                    "page_img": page_img_url,
                    "last_kind": "stem",
                }
            else:
                cur_q["stem_lines"].append(text)

    flush_q(cur_q)
    return inserted


def parse_neuro_blanc(conn) -> int:
    """Parse EXAMEN BLANC NEUROLOGIE 2025 + CORRECTION EXAMEN BLANC NEUROLOGIE 2025 into full QROC questions."""
    q_file = conn.execute("SELECT id, local_path FROM drive_files WHERE id = '1tZanePTijMdq2R3oxDex5M_silBKW9pv'").fetchone()
    c_file = conn.execute("SELECT id, local_path FROM drive_files WHERE id = '1txbPJHd7__WWGC94pdXuUWmVQYprxYzp'").fetchone()
    if not c_file or not c_file["local_path"]:
        return 0
    txt = subprocess.check_output(["pdftotext", str(DATA_DIR / c_file["local_path"]), "-"]).decode("utf-8", errors="ignore")
    lines = [ln.rstrip() for ln in txt.splitlines()]

    topic = "AVCI"
    items: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None

    for raw in lines:
        s = raw.strip()
        if not s or "CORRECTION EXAMEN BLANC" in s:
            continue
        if s.startswith("\uf076") or s.startswith("") or (len(s) < 45 and not re.match(r"^\d+[\.-]", s) and not s.startswith(("•", "-", "o", "", "➢")) and s.isupper()):
            topic = re.sub(r"^[^\wÀ-ÿ]+", "", s).strip()
            continue
        qm = re.match(r"^(\d+)[\.-]\s*(.+)$", s)
        if qm:
            if cur:
                items.append(cur)
            cur = {"topic": topic, "num": int(qm.group(1)), "stem": qm.group(2).strip(), "bullets": []}
        elif cur:
            clean_b = re.sub(r"^[•\-o▪➢\uf0b7\uf0d8\s]+", "", s).strip()
            if clean_b:
                cur["bullets"].append(clean_b)
    if cur:
        items.append(cur)

    inserted = 0
    for idx, it in enumerate(items, 1):
        cid = find_best_course_id(conn, "neuro-neurochir", f"{it['topic']} {it['stem']}")
        rubric = {"points": it["bullets"][:18]}
        expl = "Correction officielle Examen Blanc Neurologie 2025 :\n• " + "\n• ".join(it["bullets"][:14])
        conn.execute(
            """
            INSERT INTO questions (
                external_key, module_id, sub_discipline, course_id, professor, source_file_id,
                source_label, exam_year, session, question_number, question_type, stem,
                statements_json, options_json, correct_answers_json, rubric_json, explanation,
                verification_status, frequency_tag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', '[]', '[]', ?, ?, 'verified_key', 'sn_2025_repeat')
            ON CONFLICT(external_key) DO UPDATE SET
                stem=excluded.stem,
                rubric_json=excluded.rubric_json,
                explanation=excluded.explanation
            """,
            (
                f"neuro_blanc_2025_{idx}", "neuro-neurochir", "Neurologie", cid, "Prof Mabrouk / Yousfi / El Hassnaoui / Benyarou",
                c_file["id"], "EXAMEN BLANC NEURO 2025 (Corrigé)", "2025", "Blanc", idx, "qroc",
                f"[{it['topic']}] {it['stem']}",
                json.dumps(rubric, ensure_ascii=False),
                expl,
            ),
        )
        inserted += 1
    return inserted


def parse_quiz_amphi_and_unkeyed(conn) -> int:
    """Parse QUIZ_Amphi_Dermato.pdf (75 QCMs) + BOUICHRAT NC + HALAOUI NC cleanly."""
    inserted = 0
    # 1. QUIZ_Amphi
    row = conn.execute("SELECT id, local_path FROM drive_files WHERE id = '1YYWiuY2fKL-WC7ipbgtXzF-jp3zO0zg-'").fetchone()
    parsed_items: list[dict[str, Any]] = []
    if row and row["local_path"]:
        pdf_p = DATA_DIR / row["local_path"]
        pages_raw = subprocess.check_output(["pdftotext", str(pdf_p), "-"]).decode("utf-8", errors="ignore").split("\x0c")
        topics_map = [
            (2, "Acné"), (11, "Psoriasis"), (22, "Rosacée"), (33, "Urticaire"),
            (40, "Toxidermies"), (51, "Tuberculose cutanée & Lèpre"), (65, "HPV & Érythème noueux"),
        ]
        for pno, ptxt in enumerate(pages_raw, 1):
            t_label = "Dermatologie (Prof Zerrouki)"
            for min_p, tl in topics_map:
                if pno >= min_p:
                    t_label = tl
            lines = [re.sub(r"\s+", " ", x).strip() for x in ptxt.splitlines() if x.strip()]
            opts = []
            stem_parts = []
            for ln in lines:
                om = OPT_LINE_RE.match(ln)
                if om:
                    opts.append({"letter": om.group(1), "text": om.group(2)})
                elif not re.fullmatch(r"\d+", ln) and "QCM" not in ln.upper():
                    if opts:
                        opts[-1]["text"] += " " + ln
                    else:
                        stem_parts.append(ln)
            if len(opts) >= 3 and stem_parts:
                parsed_items.append({
                    "ext_key": f"quiz_amphi_p{pno}",
                    "mod_id": "endocrino-dermato",
                    "sub": "Dermatologie",
                    "prof": "Prof Zerrouki",
                    "file_id": row["id"],
                    "label": "QUIZ Amphi Dermato",
                    "session": "Quiz Amphi",
                    "num": len(parsed_items) + 1,
                    "topic": t_label,
                    "stem": " ".join(stem_parts),
                    "options": opts,
                })

    # 2. Unkeyed text QEs (Bouichrat NC & Halaoui NC)
    for slug, fid, mod_id, sub, prof, label, sess in UNKEYED_TEXT_QES:
        r = conn.execute("SELECT local_path FROM drive_files WHERE id = ?", (fid,)).fetchone()
        if not r or not r["local_path"]:
            continue
        txt = subprocess.check_output(["pdftotext", str(DATA_DIR / r["local_path"]), "-"]).decode("utf-8", errors="ignore")
        lines = [re.sub(r"\s+", " ", x).strip() for x in txt.splitlines() if x.strip()]
        stem_buf: list[str] = []
        opts: list[dict[str, str]] = []
        topic = sub
        q_cnt = 0
        for ln in lines:
            if re.match(r"^(ANATOMIE|ENDOCRINOLOGIE)\b", ln):
                continue
            om = OPT_LINE_RE.match(ln)
            if om:
                opts.append({"letter": om.group(1), "text": om.group(2)})
            else:
                if opts:
                    q_cnt += 1
                    parsed_items.append({
                        "ext_key": f"{slug}_{q_cnt}",
                        "mod_id": mod_id, "sub": sub, "prof": prof, "file_id": fid,
                        "label": label, "session": sess, "num": q_cnt, "topic": topic,
                        "stem": " ".join(stem_buf) or topic, "options": opts,
                    })
                    opts = []
                    stem_buf = []
                if ln.endswith(":") and not ln.lower().startswith(("concernant", "parmi", "quelles", "quels", "devant")):
                    topic = ln.rstrip(":")
                else:
                    stem_buf.append(ln)
        if opts:
            q_cnt += 1
            parsed_items.append({
                "ext_key": f"{slug}_{q_cnt}",
                "mod_id": mod_id, "sub": sub, "prof": prof, "file_id": fid,
                "label": label, "session": sess, "num": q_cnt, "topic": topic,
                "stem": " ".join(stem_buf) or topic, "options": opts,
            })

    # Batch-verify unkeyed items cleanly via Gemini JSON cache if needed
    cache_file = DATA_DIR / "scans" / "unkeyed_answers_cache.json"
    ans_cache: dict[str, Any] = json.loads(cache_file.read_text()) if cache_file.exists() else {}
    missing = [it for it in parsed_items if it["ext_key"] not in ans_cache]
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if missing and key:
        print(f"Generating medical verification keys for {len(missing)} unkeyed QUIZ Amphi / Halaoui / Bouichrat QCMs...")
        for i in range(0, len(missing), 25):
            batch = missing[i : i + 25]
            payload_qs = [
                {
                    "id": b["ext_key"],
                    "topic": b["topic"],
                    "stem": b["stem"],
                    "options": b["options"],
                }
                for b in batch
            ]
            prompt = (
                "Tu es professeur agrégé en médecine FMPO (Maroc, ECN/S7). Pour chaque QCM ci-dessous, "
                "donne les lettres EXACTES justes et une brève justification (1-2 phrases) conforme aux cours FMPO/ECN.\n"
                "Réponds uniquement en JSON: {\"answers\": [{\"id\": \"...\", \"correct\": [\"A\", \"C\"], \"explanation\": \"...\"}]}\n\n"
                + json.dumps(payload_qs, ensure_ascii=False)
            )
            for model in ["gemini-3.1-flash-lite-preview", "gemini-3-flash-preview"]:
                req = urllib.request.Request(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
                    data=json.dumps({
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
                    }).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(req, timeout=75) as resp:
                        body = json.loads(resp.read().decode("utf-8"))
                        out = json.loads(body["candidates"][0]["content"]["parts"][0]["text"])
                        for item in out.get("answers", []):
                            ans_cache[item["id"]] = item
                        print(f"  Batch {i} OK via {model} ({len(out.get('answers', []))} answers)")
                        break
                except Exception as exc:
                    print(f"  Batch {i} {model} err: {exc}")
                    time.sleep(3)
            time.sleep(2)
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(ans_cache, ensure_ascii=False, indent=2), encoding="utf-8")

    for it in parsed_items:
        cid = find_best_course_id(conn, it["mod_id"], f"{it['topic']} {it['stem']}")
        ans = ans_cache.get(it["ext_key"], {})
        corr = [c.upper() for c in ans.get("correct", [])]
        expl = ans.get("explanation", "")
        status = "ai_verified" if corr else "unverified"
        conn.execute(
            """
            INSERT INTO questions (
                external_key, module_id, sub_discipline, course_id, professor, source_file_id,
                source_label, exam_year, session, question_number, question_type, stem,
                statements_json, options_json, correct_answers_json, rubric_json, explanation,
                verification_status, frequency_tag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'qcm_multi', ?, '[]', ?, ?, '{}', ?, ?, 'high_yield')
            ON CONFLICT(external_key) DO UPDATE SET
                correct_answers_json=excluded.correct_answers_json,
                explanation=excluded.explanation,
                verification_status=excluded.verification_status
            """,
            (
                it["ext_key"], it["mod_id"], it["sub"], cid, it["prof"], it["file_id"],
                it["label"], "2026", it["session"], it["num"], f"[{it['topic']}] {it['stem']}",
                json.dumps(it["options"], ensure_ascii=False),
                json.dumps(corr, ensure_ascii=False),
                expl, status,
            ),
        )
        inserted += 1
    return inserted


def main() -> None:
    init_db(DB_PATH)
    conn = get_conn(DB_PATH)
    conn.execute("DELETE FROM questions WHERE session IN ('QE', 'Blanc', 'Quiz Amphi') AND source_label NOT IN ('CORRECTION EXAMEN BLANC ENDOCRINO', 'QE PR SADKI (Corrigé)', 'QE PR KHOULALI (Corrigé)')")
    total = 0
    for args in HIGHLIGHT_CORRIGES:
        cnt = parse_highlight_pdf(conn, *args)
        print(f"Parsed {args[0]}: {cnt} questions")
        total += cnt
    nb = parse_neuro_blanc(conn)
    print(f"Parsed Neuro Blanc 2025: {nb} questions")
    total += nb
    uk = parse_quiz_amphi_and_unkeyed(conn)
    print(f"Parsed Quiz Amphi + Bouichrat + Halaoui: {uk} questions")
    total += uk
    conn.commit()
    conn.close()
    print(f"TOTAL QE/Quiz questions ingested: {total}")


if __name__ == "__main__":
    main()
