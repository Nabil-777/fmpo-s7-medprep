#!/usr/bin/env python3
"""Digitize all scanned 2025 SN exams & key scanned Corrigés into SQLite (with disk JSON cache)."""
from __future__ import annotations

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.db import DATA_DIR, DB_PATH, get_conn, init_db  # noqa: E402
from pipeline.ingest_inventory import norm, token_score  # noqa: E402
from pipeline.ocr_scanner import digitize_image_page, render_pdf_pages  # noqa: E402

SCANS_DIR = DATA_DIR / "scans"

SN_CONFIG = [
    ("aps", "anapath", "Anatomopathologie", "EXAMEN APS 2025 SN", "1T1pWkV6ULtUSjQ3QGYpwNHCSWOJ7xj0f"),
    ("endo", "endocrino-dermato", "Endocrinologie", "EXAMEN ENDOCRINO 2025 SN", "1uEU_UaRXMvOWzLKHyg6H10ZFeWgkKpvd"),
    ("derm", "endocrino-dermato", "Dermatologie", "EXAMEN DERMATO 2025 SN", "1ut6iSVe76R34C0W5bGo7c9r1jCvwVj-f"),
    ("hemato", "hemato-onco", "Hématologie", "EXAMEN HEMATO ONCO 2025 SN", "1LXR57TSN4JpH0cAsTnsNJEomz4i8H-CC"),
    ("neuro", "neuro-neurochir", "Neurologie", "EXAMEN NEURO NEUROCHIR 2025 SN", "1yDIe_04crG9EVyK8GE9sXZjyLVNom2kw"),
]

EXTRA_SCANNED_CORRIGES = [
    (
        "eb_endo_c",
        "1mx4lD1Cyb39KNbV1NQkHde-lkVpMByz6",
        "endocrino-dermato",
        "Endocrinologie",
        "CORRECTION EXAMEN BLANC ENDOCRINO",
        "Blanc",
    ),
    (
        "sadki_c",
        "1ucKQAHj_H1lIASnAjgjrXYz99wqM2vSf",
        "hemato-onco",
        "Hématologie",
        "QE PR SADKI (Corrigé)",
        "QE",
    ),
    (
        "khoulali_c",
        "1ydeIVCnonlGbG1-LPzYt77WcQbdJ2gBe",
        "neuro-neurochir",
        "Neurochirurgie",
        "QE PR KHOULALI (Corrigé)",
        "QE",
    ),
]


def _page_num_from_name(name: str) -> int:
    m = re.search(r"(\d+)\.png$", name)
    return int(m.group(1)) if m else 0


def ocr_batch(tasks: list[tuple[Path, Path, str]]) -> None:
    """Run Vision OCR concurrently for uncached PNG pages."""
    todo = [(img, cache_p, hint) for (img, cache_p, hint) in tasks if not cache_p.exists()]
    if not todo:
        return
    print(f"Running Vision OCR on {len(todo)} uncached scan pages...")
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = {ex.submit(digitize_image_page, img, hint): (img, cache_p) for img, cache_p, hint in todo}
        for fut in as_completed(futs):
            img, cache_p = futs[fut]
            cache_p.parent.mkdir(parents=True, exist_ok=True)
            try:
                res = fut.result()
                cache_p.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"  OCR OK: {img.name} ({len(res.get('questions', []))} q)")
            except Exception as exc:
                print(f"  OCR ERR {img.name}: {exc}")


def match_course(conn, mod_id: str, text: str) -> int | None:
    rows = conn.execute("SELECT id, professor, canonical_title FROM courses WHERE module_id = ?", (mod_id,)).fetchall()
    best_id = None
    best_sc = 0.0
    for r in rows:
        sc = token_score(r["canonical_title"], text, r["professor"], None)
        if sc > best_sc:
            best_sc = sc
            best_id = r["id"]
    return best_id if best_sc >= 0.3 else None


def ingest_cached_pages(conn) -> int:
    inserted = 0

    # 1. All 5 2025 SN exams
    sn_json_dir = SCANS_DIR / "sn2025_json"
    sn_png_dir = SCANS_DIR / "sn2025"

    for prefix, mod_id, default_sub, source_label, file_id in SN_CONFIG:
        pages = sorted(sn_png_dir.glob(f"{prefix}-*.png"), key=lambda p: _page_num_from_name(p.name))
        active_vignette = None
        last_qnum = 0
        for img in pages:
            jp = sn_json_dir / f"{img.stem}.json"
            if not jp.exists():
                continue
            data = json.loads(jp.read_text(encoding="utf-8"))
            for idx, q in enumerate(data.get("questions", []), 1):
                if q.get("vignette_text"):
                    active_vignette = q["vignette_text"].strip()
                qnum = q.get("question_number") or (last_qnum + 1)
                last_qnum = int(qnum) if isinstance(qnum, int) else last_qnum + 1
                sub = default_sub
                if prefix == "hemato" and (last_qnum in (21, 22, 23, 24, 25, 31, 32, 33, 34, 35) or "onco" in norm(q.get("stem", "")) or "cancer" in norm(q.get("stem", "")) or "radioth" in norm(q.get("stem", ""))):
                    sub = "Oncologie"
                if prefix == "neuro" and ("adénome" in norm(q.get("stem", "")) or "dorsale" in norm(q.get("stem", "")) or "médullaire" in norm(q.get("stem", "")) or "copie 1" in norm(str(qnum)) or "copie 2" in norm(str(qnum))):
                    sub = "Neurochirurgie"

                qtype = q.get("question_type") or ("qcm_group" if prefix == "aps" else ("qroc" if prefix == "neuro" else "qcm_multi"))
                if prefix == "aps":
                    qtype = "qcm_group"
                elif prefix in ("endo", "derm", "hemato"):
                    qtype = "qcm_multi"

                mistake_flag = bool(q.get("student_mistake_flag"))
                corr = q.get("verified_correct_letters") or q.get("margin_correct_letters") or q.get("marked_letters") or []
                if isinstance(corr, str):
                    corr = list(corr)
                corr = [c.strip().upper() for c in corr if c.strip()]

                status = "student_mistake_flagged" if mistake_flag else "verified_key"
                stem = (q.get("stem") or "").strip()
                if not stem:
                    continue
                notes = (q.get("handwritten_notes") or "").strip()
                expl = (q.get("explanation") or "").strip()
                if notes and notes not in expl:
                    expl = f"Annotation scan : {notes}\n{expl}".strip()

                rubric = {"points": q.get("rubric_points", [])}
                ext_key = f"sn2025_{prefix}_p{img.stem}_q{qnum}_{idx}"
                cid = match_course(conn, mod_id, f"{stem} {active_vignette or ''}")

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
                        rubric_json=excluded.rubric_json,
                        explanation=excluded.explanation,
                        verification_status=excluded.verification_status,
                        course_id=COALESCE(excluded.course_id, questions.course_id)
                    """,
                    (
                        ext_key, mod_id, sub, cid, None, file_id,
                        source_label, "2025", "SN", last_qnum,
                        f"sn2025_{prefix}_vig" if active_vignette else None,
                        active_vignette,
                        qtype, stem,
                        json.dumps(q.get("statements") or [], ensure_ascii=False),
                        json.dumps(q.get("options") or [], ensure_ascii=False),
                        json.dumps(corr, ensure_ascii=False),
                        json.dumps(rubric, ensure_ascii=False),
                        expl,
                        status,
                        f"/api/scans/sn2025/{img.name}",
                        "sn_2025_core",
                    ),
                )
                inserted += 1

    # 2. Extra scanned Corrigés
    for slug, file_id, mod_id, sub, label, sess in EXTRA_SCANNED_CORRIGES:
        png_dir = SCANS_DIR / slug
        json_dir = SCANS_DIR / f"{slug}_json"
        if not json_dir.exists():
            continue
        pages = sorted(png_dir.glob("*.png"), key=lambda p: _page_num_from_name(p.name))
        q_counter = 0
        active_vig = None
        for img in pages:
            jp = json_dir / f"{img.stem}.json"
            if not jp.exists():
                continue
            data = json.loads(jp.read_text(encoding="utf-8"))
            for q in data.get("questions", []):
                q_counter += 1
                if q.get("vignette_text"):
                    active_vig = q["vignette_text"].strip()
                stem = (q.get("stem") or "").strip()
                if not stem:
                    continue
                corr = q.get("verified_correct_letters") or q.get("marked_letters") or []
                if isinstance(corr, str):
                    corr = list(corr)
                corr = [c.strip().upper() for c in corr if c.strip()]
                qtype = q.get("question_type") or "qcm_multi"
                if slug == "khoulali_c":
                    qtype = "qroc"
                rubric = {"points": q.get("rubric_points", [])}
                ext_key = f"{slug}_{img.stem}_{q_counter}"
                cid = match_course(conn, mod_id, f"{stem} {active_vig or ''}")
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
                        options_json=excluded.options_json,
                        correct_answers_json=excluded.correct_answers_json,
                        rubric_json=excluded.rubric_json,
                        explanation=excluded.explanation
                    """,
                    (
                        ext_key, mod_id, sub, cid,
                        "Prof Sadki" if slug == "sadki_c" else ("Prof Khoulali" if slug == "khoulali_c" else None),
                        file_id, label, "2025", sess, q_counter,
                        f"{slug}_vig" if active_vig else None,
                        active_vig,
                        qtype, stem,
                        json.dumps(q.get("statements") or [], ensure_ascii=False),
                        json.dumps(q.get("options") or [], ensure_ascii=False),
                        json.dumps(corr, ensure_ascii=False),
                        json.dumps(rubric, ensure_ascii=False),
                        (q.get("explanation") or "").strip(),
                        "corrigé_raster",
                        f"/api/scans/{slug}/{img.name}",
                        "high_yield",
                    ),
                )
                inserted += 1

    return inserted


def main() -> None:
    init_db(DB_PATH)
    conn = get_conn(DB_PATH)

    tasks: list[tuple[Path, Path, str]] = []
    # SN 2025 pages (already rendered in data/scans/sn2025)
    sn_dir = SCANS_DIR / "sn2025"
    sn_json = SCANS_DIR / "sn2025_json"
    sn_hints = {
        "aps": "EXAMEN APS 2025 SN (Anatomopathologie, QCM à groupements a-e et choix A-E, corrigé annoté vert/X)",
        "endo": "EXAMEN ENDOCRINO 2025 SN (Endocrinologie, QCM multi-réponses, vignette grossesse/hypothyroïdie incluse)",
        "derm": "EXAMEN DERMATO 2025 SN (Dermatologie Q23-52, QCM multi-réponses, marge droite = réponses vertes)",
        "hemato": "EXAMEN HEMATO-ONCO 2025 SN (Hématologie-Oncologie Q1-35, QCM multi-réponses, annotations vert/rouge)",
        "neuro": "EXAMEN NEURO-NEUROCHIR 2025 SN (Épreuve rédactionnelle Copie 1, 2, 3 : QROC, cas clinique, synthèse)",
    }
    for prefix, _, _, _, _ in SN_CONFIG:
        for img in sorted(sn_dir.glob(f"{prefix}-*.png"), key=lambda p: _page_num_from_name(p.name)):
            tasks.append((img, sn_json / f"{img.stem}.json", sn_hints[prefix]))

    # Render & OCR extra short scanned corrigés from drive_cache
    for slug, file_id, _, sub, label, _ in EXTRA_SCANNED_CORRIGES:
        row = conn.execute("SELECT local_path FROM drive_files WHERE id = ?", (file_id,)).fetchone()
        if not row or not row["local_path"]:
            continue
        pdf_p = DATA_DIR / row["local_path"]
        png_dir = SCANS_DIR / slug
        json_dir = SCANS_DIR / f"{slug}_json"
        if not list(png_dir.glob("*.png")):
            render_pdf_pages(pdf_p, png_dir, dpi=130, prefix="page")
        for img in sorted(png_dir.glob("*.png"), key=lambda p: _page_num_from_name(p.name)):
            tasks.append((img, json_dir / f"{img.stem}.json", f"{label} ({sub})"))

    ocr_batch(tasks)
    count = ingest_cached_pages(conn)
    conn.commit()
    conn.close()
    print(f"Digitized & ingested {count} scanned exam/corrigé questions.")


if __name__ == "__main__":
    main()
