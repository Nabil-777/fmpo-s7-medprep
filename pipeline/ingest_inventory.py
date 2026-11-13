#!/usr/bin/env python3
"""Ingest S7 Excel tracker, Drive inventory JSON, and local course text/slide outlines."""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

import docx
import openpyxl
import pypdf
from pptx import Presentation

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.db import DATA_DIR, DB_PATH, get_conn, init_db  # noqa: E402

MODULES = [
    {
        "id": "neuro-neurochir",
        "name": "Neurologie & Neurochirurgie",
        "short_name": "Neuro-NeuroChir",
        "sub_disciplines": json.dumps(["Neurologie", "Neurochirurgie"], ensure_ascii=False),
        "exam_format": "QROC + Cas clinique + Question de synthèse (Rédactionnel pur)",
        "exam_duration_min": 60,
        "scoring_rule": "60% Neurologie / 40% Neurochirurgie · Note éliminatoire < 5/20 dans un élément",
        "accent_color": "indigo",
    },
    {
        "id": "endocrino-dermato",
        "name": "Endocrinologie & Dermatologie",
        "short_name": "Endocrino-Dermato",
        "sub_disciplines": json.dumps(["Endocrinologie", "Dermatologie"], ensure_ascii=False),
        "exam_format": "QCM multi-réponses + Vignettes cliniques séquentielles",
        "exam_duration_min": 55,
        "scoring_rule": "50% Endocrinologie (25 min / 22 QCM) + 50% Dermatologie (30 min / 30 QCM)",
        "accent_color": "amber",
    },
    {
        "id": "hemato-onco",
        "name": "Hématologie & Oncologie",
        "short_name": "Hémato-Onco",
        "sub_disciplines": json.dumps(["Hématologie", "Oncologie"], ensure_ascii=False),
        "exam_format": "QCM multi-réponses (Tout ou rien / partiel selon barème)",
        "exam_duration_min": 45,
        "scoring_rule": "35 QCM mixtes Hématologie + Oncologie médicale & chirurgicale",
        "accent_color": "rose",
    },
    {
        "id": "anapath",
        "name": "Anatomopathologie Spécialisée (APS)",
        "short_name": "Anapath (APS)",
        "sub_disciplines": json.dumps(["Anatomopathologie"], ensure_ascii=False),
        "exam_format": "QCM à groupements (Propositions a-e → Choix unique A-E)",
        "exam_duration_min": 60,
        "scoring_rule": "30 QCM à groupements (binaire par question)",
        "accent_color": "emerald",
    },
]

HIGH_FREQ_KEYWORDS = [
    "avci", "thrombophlebite", "myasthenie", "parkinson", "hypophysaire", "spondylodiscite",
    "compression medullaire", "hypothyroidie", "hyperthyroidie", "insuffisance surrenalienne",
    "hypercalcemie", "hypocalcemie", "diabete", "dyslipidemie", "nutrition",
    "pemphigus", "psoriasis", "syphilis", "herpes", "varicelle", "zona", "toxidermie", "erytheme",
    "leucemie", "myelome", "waldenstrom", "polyglobulie", "myelofibrose", "ferriprive",
    "hemolytique", "transfusion", "urgences oncologiques", "cancer",
    "gastrite", "estomac", "thyroide", "vessie", "colon", "colorectal", "sein", "prostate",
]


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return text.strip()


def map_module(raw_mod: str, raw_sub: str = "") -> tuple[str, str]:
    m = norm(raw_mod)
    s = norm(raw_sub)
    if "neuro" in m or "neuro" in s:
        sub = "Neurochirurgie" if "chir" in s else "Neurologie"
        return "neuro-neurochir", sub
    if "endocrino" in m or "dermato" in m or "endocrino" in s or "dermato" in s:
        sub = "Dermatologie" if "dermato" in s else "Endocrinologie"
        return "endocrino-dermato", sub
    if "hemato" in m or "onco" in m or "hemato" in s or "onco" in s:
        sub = "Oncologie" if "onco" in s else "Hématologie"
        return "hemato-onco", sub
    return "anapath", "Anatomopathologie"


def clean_prof(raw: str) -> str:
    s = (raw or "").replace("✔", "").strip()
    s = re.sub(r"\s+", " ", s)
    if not s:
        return "Non précisé"
    return s.title().replace("Pr.", "Prof ").replace("Prof.", "Prof ").strip()


def clean_flag(avancement: str | None, support: str | None, prof: str) -> tuple[str, str]:
    av = norm(avancement or "")
    sup = norm(support or "")
    if av in ("v", "fait", "valide"):
        promo = "V"
    elif "cours" in av:
        promo = "en_cours"
    else:
        promo = "none"

    if "sans support" in sup:
        flag = "sans_support"
    elif sup == "nv support" or ("nv support" in sup and "recupere" not in sup):
        flag = "nv_support_missing"
    elif "recupere" in sup or "nv" in sup:
        flag = "updated_2026"
    else:
        flag = "ok"
    return promo, flag


def classify_drive_file(path: str) -> tuple[str, str, str | None, bool]:
    p_norm = norm(path)
    # Determine module
    if "anatomopathologie" in p_norm or "/aps/" in p_norm or " aps " in p_norm:
        mod = "anapath"
    elif "dermato" in p_norm or "endocrino" in p_norm:
        mod = "endocrino-dermato"
    elif "hemato" in p_norm or "onco" in p_norm:
        mod = "hemato-onco"
    elif "neuro" in p_norm:
        mod = "neuro-neurochir"
    else:
        mod = "general"

    is_corrige = "corriges" in p_norm.split() or "correction" in p_norm
    if "examen 2025 sn" in p_norm:
        cat = "examen_sn"
    elif "corriges" in p_norm.split():
        cat = "corrige"
    elif "non corriges" in p_norm:
        cat = "non_corrige"
    elif "resumer mohamed jrh" in p_norm:
        cat = "resume_mohamed"
    elif "quiz amphi" in p_norm:
        cat = "quiz_amphi"
    elif "programme" in p_norm or "check_promo" in p_norm or "check promo" in p_norm:
        cat = "programme"
    else:
        cat = "cours"

    prof = None
    m = re.search(r"pr(?:of)?\.?\s+([a-zA-Zéèêàîïôùç-]+)", path, flags=re.IGNORECASE)
    if m:
        prof = f"Prof {m.group(1).strip().title()}"
    elif "bouichrat" in p_norm:
        prof = "Prof Bouichrat"
    elif "latrech" in p_norm:
        prof = "Prof Latrech"
    elif "rouf" in p_norm:
        prof = "Prof Rouf"
    elif "zerrouki" in p_norm:
        prof = "Prof Zerrouki"
    elif "zizi" in p_norm:
        prof = "Prof Zizi"
    elif "alaoui" in p_norm:
        prof = "Prof Alaoui"
    elif "hamaz" in p_norm:
        prof = "Prof Hamaz"
    elif "serraj" in p_norm:
        prof = "Prof Serraj"
    elif "sadki" in p_norm:
        prof = "Prof Sadki"
    elif "aqodad" in p_norm:
        prof = "Prof Aqodad"
    elif "sabri" in p_norm:
        prof = "Prof Sabri"
    elif "afkir" in p_norm or "afaik" in p_norm or "afqir" in p_norm:
        prof = "Prof Afkir"
    elif "mezouar" in p_norm:
        prof = "Prof Mezouar"
    elif "bennani" in p_norm:
        prof = "Prof Bennani"
    elif "halaoui" in p_norm:
        prof = "Prof Halaoui"
    elif "khoulali" in p_norm:
        prof = "Prof Khoulali"
    elif "khay" in p_norm:
        prof = "Prof Khay"
    elif "raouzi" in p_norm:
        prof = "Prof Raouzi"
    elif "elhasnaoui" in p_norm or "hassnaoui" in p_norm:
        prof = "Prof El Hassnaoui"
    elif "mebrouk" in p_norm or "mabrouk" in p_norm:
        prof = "Prof Mabrouk"

    return mod, cat, prof, is_corrige


def extract_file_metadata_and_text(local_path: Path) -> tuple[int, int, str]:
    """Return (text_chars, page_count, extracted_preview)."""
    if not local_path.exists():
        return 0, 0, ""
    ext = local_path.suffix.lower()
    try:
        if ext == ".pdf":
            reader = pypdf.PdfReader(str(local_path))
            pages = len(reader.pages)
            chunks = []
            total = 0
            for i, pg in enumerate(reader.pages):
                t = (pg.extract_text() or "").strip()
                total += len(t)
                if len("\n".join(chunks)) < 12000 and t:
                    chunks.append(f"--- Page {i+1} ---\n{t}")
            return total, pages, "\n\n".join(chunks)[:12000]
        if ext == ".pptx":
            prs = Presentation(str(local_path))
            slides_txt = []
            total = 0
            for idx, slide in enumerate(prs.slides, 1):
                parts = []
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        parts.append(shape.text.strip())
                st = "\n".join(parts)
                total += len(st)
                if st and len("\n".join(slides_txt)) < 12000:
                    slides_txt.append(f"### Slide {idx}\n{st}")
            return total, len(prs.slides), "\n\n".join(slides_txt)[:12000]
        if ext == ".docx":
            doc = docx.Document(str(local_path))
            paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
            full = "\n".join(paras)
            return len(full), max(1, len(paras) // 25), full[:12000]
    except Exception:
        return 0, 0, ""
    return 0, 0, ""


def extract_high_yield_bullets(text: str, title: str) -> list[str]:
    if not text:
        return []
    lines = [re.sub(r"\s+", " ", ln).strip("•▪-– \t") for ln in text.splitlines()]
    bullets: list[str] = []
    seen = set()
    for ln in lines:
        if len(ln) < 32 or len(ln) > 220 or ln.endswith(":"):
            continue
        if ln.startswith("---") or ln.startswith("###") or "université" in ln.lower() or "faculté" in ln.lower():
            continue
        low = ln.lower()
        if any(
            kw in low
            for kw in (
                "diagnostic", "traitement", "indication", "contre-indication",
                "clinique", "biologie", "irm", "scanner", "irm", "urgence",
                "critère", "classification", "complication", "étiologie", "signe",
                "positif", "pronostic", "dépistage", "objectif",
            )
        ):
            key = norm(ln)[:50]
            if key not in seen:
                seen.add(key)
                bullets.append(ln)
            if len(bullets) >= 8:
                break
    return bullets


def token_score(course_title: str, file_path: str, course_prof: str, file_prof: str | None) -> float:
    ct = set(norm(course_title).split()) - {"les", "la", "le", "de", "du", "des", "et", "en", "l", "d", "a"}
    fp = set(norm(Path(file_path).stem).split())
    if not ct:
        return 0.0
    overlap = len(ct & fp) / max(1, len(ct))
    # Special aliases
    pn = norm(course_title)
    fn = norm(file_path)
    if "hsa" in pn and ("hemorragie meningee" in fn or "meningee" in fn):
        overlap += 0.9
    if "tv" in pn or "vertebro" in pn:
        if "tvm" in fn or "vertebro" in fn:
            overlap += 0.9
    if "compression medullaire" in pn and "comp med" in fn:
        overlap += 0.9
    if "hpv" in pn or "verrue" in pn or "papillomavirus" in pn:
        if "hvp" in fn or "hpv" in fn:
            overlap += 0.85
    if "dermatoses bulleuses" in pn and "pemphigus" in fn:
        overlap += 0.5
    if "dhdnn" in fn and ("hypodermite" in pn or "noueux" in pn or "dermo" in pn):
        overlap += 0.7
    if "is" == fn.split()[-1] or " r is" in fn:
        if "surrenalienne" in pn:
            overlap += 0.85
    if " r la" in fn and "leucemies aigues" in pn:
        overlap += 0.85
    if "lmc" in fn and "myeloide chronique" in pn:
        overlap += 0.85
    if "llc" in fn and "lymphoide chronique" in pn:
        overlap += 0.85
    if "lnh" in fn and "non hodgkinien" in pn:
        overlap += 0.85
    if "lh" in fn.split() and "hodgkin" in pn:
        overlap += 0.85
    if "sep" in fn.split() and "sclerose en plaques" in pn:
        overlap += 0.85
    if "pheo" in fn and ("pheochromocytome" in pn or "htae" in pn):
        overlap += 0.75
    if "foie" in fn and ("hepatique" in pn or "foie" in pn):
        overlap += 0.7
    if "estomac" in fn and ("gastrique" in pn or "estomac" in pn):
        overlap += 0.8
    if "broncho" in fn and "bronchique" in pn:
        overlap += 0.8
    if course_prof and file_prof and norm(course_prof).split()[-1] == norm(file_prof).split()[-1]:
        overlap += 0.25
    return overlap


def main() -> None:
    init_db(DB_PATH)
    conn = get_conn(DB_PATH)

    # 1. Seed modules
    for m in MODULES:
        conn.execute(
            """
            INSERT INTO modules (id, name, short_name, sub_disciplines, exam_format, exam_duration_min, scoring_rule, accent_color)
            VALUES (:id, :name, :short_name, :sub_disciplines, :exam_format, :exam_duration_min, :scoring_rule, :accent_color)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                short_name=excluded.short_name,
                sub_disciplines=excluded.sub_disciplines,
                exam_format=excluded.exam_format,
                exam_duration_min=excluded.exam_duration_min,
                scoring_rule=excluded.scoring_rule,
                accent_color=excluded.accent_color
            """,
            m,
        )

    # 2. Parse Excel tracker into courses
    wb = openpyxl.load_workbook(DATA_DIR / "S7_check_promo_2023_restructure.xlsx", data_only=True)
    ws = wb["Sheet1"]

    conn.execute("DELETE FROM courses")
    cur_mod = cur_sub = cur_prof = ""
    course_rows = []
    order = 0
    for r in range(2, ws.max_row + 1):
        m, s, p, c, av, sup, _ = [ws.cell(r, col).value for col in range(1, 8)]
        if m:
            cur_mod = str(m).strip()
        if s:
            cur_sub = str(s).strip()
        if p:
            cur_prof = clean_prof(str(p))
        if c:
            raw_title = str(c).strip()
            mod_id, sub_disp = map_module(cur_mod, cur_sub)
            promo_status, upload_flag = clean_flag(
                str(av) if av is not None else None,
                str(sup) if sup is not None else None,
                cur_prof,
            )
            freq = "high_yield" if any(k in norm(raw_title) for k in HIGH_FREQ_KEYWORDS) else "standard"
            order += 1
            cur = conn.execute(
                """
                INSERT INTO courses (module_id, sub_discipline, professor, canonical_title, raw_tracker_title,
                                     promo_status, upload_flag, row_order, exam_frequency)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (mod_id, sub_disp, cur_prof, raw_title, raw_title, promo_status, upload_flag, order, freq),
            )
            course_rows.append((cur.lastrowid, mod_id, sub_disp, cur_prof, raw_title))

    # 3. Parse full_inventory.json into drive_files and match courses
    inv = json.loads((DATA_DIR / "full_inventory.json").read_text())
    files = [n for n in inv["nodes"] if n["kind"] == "file"]
    cache_by_id = DATA_DIR / "drive_cache" / "by_id"

    conn.execute("DELETE FROM drive_files")
    course_texts: dict[int, list[str]] = {}

    for f in files:
        fid = f["id"]
        path = f["path"]
        name = f["name"]
        mod_id, cat, file_prof, is_corrige = classify_drive_file(path)
        local_p = cache_by_id / fid / name
        rel_local = str(local_p.relative_to(DATA_DIR)) if local_p.exists() else None
        text_chars, page_count, preview = extract_file_metadata_and_text(local_p) if local_p.exists() else (0, 0, "")
        is_scanned = 1 if (local_p.exists() and name.lower().endswith(".pdf") and page_count > 0 and text_chars < 60) else 0

        version_tag = None
        if "2026" in name:
            version_tag = "2026-2027"
        elif "final" in name.lower():
            version_tag = "final"
        elif "modified" in name.lower() or "modifiés" in path.lower():
            version_tag = "modifié"

        # Match best course
        best_cid = None
        best_score = 0.0
        if cat in ("cours", "resume_mohamed"):
            for cid, cmod, _, cprof, ctitle in course_rows:
                if mod_id != "general" and cmod != mod_id:
                    continue
                sc = token_score(ctitle, path, cprof, file_prof)
                if sc > best_score:
                    best_score = sc
                    best_cid = cid
            if best_score < 0.42:
                best_cid = None

        if best_cid and preview and cat == "cours":
            course_texts.setdefault(best_cid, []).append(f"## Source : {name}\n\n{preview[:5500]}")

        conn.execute(
            """
            INSERT INTO drive_files (id, name, path, size, modified_time, module_id, category, professor,
                                     course_id, local_path, text_chars, page_count, is_scanned, is_corrige,
                                     version_tag, extracted_preview)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fid, name, path, f.get("size", 0), f.get("modifiedTime"), mod_id, cat, file_prof,
                best_cid, rel_local, text_chars, page_count, is_scanned, int(is_corrige),
                version_tag, preview[:4000],
            ),
        )

    # 4. Populate course outlines & high-yield bullet points from extracted course text
    for cid, chunks in course_texts.items():
        combined = "\n\n".join(chunks)
        row = conn.execute("SELECT canonical_title FROM courses WHERE id = ?", (cid,)).fetchone()
        bullets = extract_high_yield_bullets(combined, row["canonical_title"] if row else "")
        conn.execute(
            "UPDATE courses SET notes_markdown = ?, high_yield_points = ? WHERE id = ?",
            (combined[:12000], json.dumps(bullets, ensure_ascii=False), cid),
        )

    conn.commit()
    stats = {
        "modules": conn.execute("SELECT COUNT(*) FROM modules").fetchone()[0],
        "courses": conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0],
        "courses_with_notes": conn.execute("SELECT COUNT(*) FROM courses WHERE length(notes_markdown) > 0").fetchone()[0],
        "drive_files": conn.execute("SELECT COUNT(*) FROM drive_files").fetchone()[0],
        "cached_files": conn.execute("SELECT COUNT(*) FROM drive_files WHERE local_path IS NOT NULL").fetchone()[0],
        "scanned_pdfs": conn.execute("SELECT COUNT(*) FROM drive_files WHERE is_scanned = 1").fetchone()[0],
    }
    conn.close()
    print("Inventory ingestion complete:", json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
