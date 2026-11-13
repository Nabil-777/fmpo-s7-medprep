#!/usr/bin/env python3
"""Download missing course/summary files via gdrive, repair course_id links, and inspect text coverage."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import docx
import pypdf
from pptx import Presentation

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.db import DATA_DIR, get_conn  # noqa: E402
from pipeline.ingest_inventory import extract_high_yield_bullets, norm, token_score  # noqa: E402

CACHE_BY_ID = DATA_DIR / "drive_cache" / "by_id"

EXPLICIT_FILE_COURSE_HINTS: list[tuple[str, str]] = [
    ("anemies ferriprives", "anemie ferriprive"),
    ("anemies hemolytiques", "anemie hemolytique"),
    ("gammapathies monoclonales", "gammapathie monoclonale"),
    ("waldenstrom", "waldenstronm"),
    ("candidoses", "candidose"),
    ("condidose", "candidose"),
    ("dermatophyties", "dermatophytes"),
    ("leishmanioses", "leishmaniose"),
    ("leichmaniose", "leishmaniose"),
    ("hypogonadisme", "hypogonadismes"),
    ("traumatismes cranioencephaliques", "trauma cranio-encephalique"),
    ("cranioencephaliques", "trauma cranio"),
    ("toxidermie", "toxidermies"),
    ("urticaire", "urticaires"),
    ("ectoparasitose", "gale"),
    ("kc du foie", "cancer du foie"),
    ("neuropathies peripheriques", "neuropathie peripherique"),
    ("tumeurs osseuses", "tumeurs osseuses"),
    ("sarcomes", "sarcomes"),
    ("r.is", "insuffisance surrenalienne"),
    ("r.la", "leucemies aigues"),
    ("rhypercalcemie", "hypercalcemie"),
    ("r. rosace", "rosacee"),
    ("r. syphylis", "syphilis"),
    ("mycose superf", "dermatophytes"),
    ("broncho-pulmonaire", "cancer du poumon"),
    ("3 lh", "lymphome de hodgkin"),
]


def _singular_tokens(text: str) -> set[str]:
    stop = {"les", "la", "le", "de", "du", "des", "et", "en", "l", "d", "a", "r", "cours", "copie", "pdf", "pptx", "modifie", "modified", "version", "finale", "final", "fmpo", "fmpo pdf"}
    out = set()
    for tok in re.split(r"[^a-z0-9]+", norm(text)):
        if not tok or tok in stop:
            continue
        if len(tok) > 4 and tok.endswith("s"):
            tok = tok[:-1]
        out.add(tok)
    return out


def improved_match_score(course_title: str, file_path: str, file_name: str, course_prof: str, file_prof: str | None) -> float:
    base = token_score(course_title, file_path, course_prof, file_prof)
    ct = _singular_tokens(course_title)
    ft = _singular_tokens(Path(file_name).stem)
    if ct and ft:
        j = len(ct & ft) / max(1, len(ct))
        if course_prof and file_prof and norm(course_prof).split()[-1] == norm(file_prof).split()[-1]:
            j += 0.12
        base = max(base, j)
    fn_norm = norm(file_name)
    cn_norm = norm(course_title)
    for f_hint, c_hint in EXPLICIT_FILE_COURSE_HINTS:
        if f_hint in fn_norm and c_hint in cn_norm:
            base = max(base, 0.95)
    return base


def extract_full_text(local_path: Path, max_chars: int = 45000) -> tuple[int, int, str]:
    """Extract clean text including PDF text layer (pdftotext fallback) & PPTX shapes/tables/notes."""
    if not local_path.exists():
        return 0, 0, ""
    ext = local_path.suffix.lower()
    if ext == ".pdf":
        pages = 0
        try:
            pages = len(pypdf.PdfReader(str(local_path)).pages)
        except Exception:
            pages = 0
        txt = ""
        try:
            txt = subprocess.check_output(["pdftotext", "-layout", str(local_path), "-"], stderr=subprocess.DEVNULL).decode("utf-8", errors="ignore")
            txt = re.sub(r"\n{3,}", "\n\n", txt).strip()
        except Exception:
            txt = ""
        if len(txt) < 100:
            try:
                reader = pypdf.PdfReader(str(local_path))
                parts = [(p.extract_text() or "").strip() for p in reader.pages]
                txt = "\n\n".join(p for p in parts if p)
            except Exception:
                pass
        return len(txt), pages, txt[:max_chars]

    if ext == ".pptx":
        try:
            prs = Presentation(str(local_path))
            blocks: list[str] = []
            total = 0
            for idx, slide in enumerate(prs.slides, 1):
                parts: list[str] = []
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        parts.append(re.sub(r"\s+", " ", shape.text).strip())
                    if getattr(shape, "has_table", False):
                        for row in shape.table.rows:
                            cells = [re.sub(r"\s+", " ", cell.text).strip() for cell in row.cells if cell.text.strip()]
                            if cells:
                                parts.append(" | ".join(cells))
                if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                    nt = slide.notes_slide.notes_text_frame.text.strip()
                    if nt:
                        parts.append(f"[Note: {nt}]")
                st = "\n".join(parts)
                total += len(st)
                if st and sum(len(b) for b in blocks) < max_chars:
                    blocks.append(f"### Slide {idx}\n{st}")
            return total, len(prs.slides), "\n\n".join(blocks)[:max_chars]
        except Exception:
            return 0, 0, ""

    if ext == ".docx":
        try:
            doc = docx.Document(str(local_path))
            paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
            for tbl in doc.tables:
                for row in tbl.rows:
                    cells = [re.sub(r"\s+", " ", c.text).strip() for c in row.cells if c.text.strip()]
                    if cells:
                        paras.append(" | ".join(cells))
            full = "\n".join(paras)
            return len(full), max(1, len(paras) // 25), full[:max_chars]
        except Exception:
            return 0, 0, ""

    return 0, 0, ""


def download_drive_file(fid: str, name: str) -> Path | None:
    dest = CACHE_BY_ID / fid / name
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    res = subprocess.run(["gdrive", "readonly", "download", fid, "--out", str(tmp)], capture_output=True, text=True, timeout=180)
    if res.returncode == 0 and tmp.exists() and tmp.stat().st_size > 0:
        tmp.rename(dest)
        return dest
    if tmp.exists():
        tmp.unlink(missing_ok=True)
    return None


def main() -> None:
    conn = get_conn()
    # Download uncached cours files (all 9) + uncached resume_mohamed files whose courses lack local text
    missing = conn.execute(
        """
        SELECT id, name, category FROM drive_files
        WHERE local_path IS NULL AND category IN ('cours', 'resume_mohamed')
        ORDER BY CASE WHEN category='cours' THEN 0 ELSE 1 END, size ASC
        """
    ).fetchall()
    print(f"Downloading {len(missing)} uncached course/summary files...")
    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = {pool.submit(download_drive_file, r["id"], r["name"]): r for r in missing}
        for fut in as_completed(futs):
            r = futs[fut]
            try:
                p = fut.result()
                if p:
                    rel = str(p.relative_to(DATA_DIR))
                    conn.execute("UPDATE drive_files SET local_path = ? WHERE id = ?", (rel, r["id"]))
                    print(f"  OK {r['category']}: {r['name']} ({p.stat().st_size // 1024} KB)")
                else:
                    print(f"  FAIL {r['category']}: {r['name']}")
            except Exception as e:
                print(f"  ERR {r['name']}: {e}")
    conn.commit()

    # Re-link all cours and resume_mohamed files & refresh extracted metadata
    courses = conn.execute("SELECT id, module_id, sub_discipline, professor, canonical_title FROM courses").fetchall()
    files = conn.execute("SELECT id, name, path, module_id, category, professor, course_id, local_path FROM drive_files WHERE category IN ('cours', 'resume_mohamed')").fetchall()

    course_chunks: dict[int, list[str]] = {}
    linked_count = 0
    for f in files:
        best_cid = f["course_id"]
        best_sc = 0.0
        for c in courses:
            if f["module_id"] != "general" and c["module_id"] != f["module_id"]:
                continue
            sc = improved_match_score(c["canonical_title"], f["path"], f["name"], c["professor"], f["professor"])
            if sc > best_sc:
                best_sc = sc
                best_cid = c["id"]
        if best_sc < 0.42:
            best_cid = f["course_id"]
        if best_cid:
            linked_count += 1

        lp = DATA_DIR / f["local_path"] if f["local_path"] else None
        tchars, pcnt, preview = extract_full_text(lp, 20000) if lp and lp.exists() else (0, 0, "")
        is_scanned = 1 if (lp and lp.exists() and f["name"].lower().endswith(".pdf") and pcnt > 0 and tchars < 150) else 0
        conn.execute(
            """
            UPDATE drive_files
            SET course_id = ?, text_chars = ?, page_count = ?, is_scanned = ?, extracted_preview = ?
            WHERE id = ?
            """,
            (best_cid, tchars, pcnt, is_scanned, preview[:8000], f["id"]),
        )
        if best_cid and preview and f["category"] == "cours":
            course_chunks.setdefault(best_cid, []).append(f"## Source : {f['name']}\n\n{preview[:7500]}")

    for cid, chunks in course_chunks.items():
        combined = "\n\n".join(chunks)
        row = conn.execute("SELECT canonical_title, high_yield_points FROM courses WHERE id = ?", (cid,)).fetchone()
        existing_hy = json.loads(row["high_yield_points"] or "[]") if row else []
        if not existing_hy:
            bullets = extract_high_yield_bullets(combined, row["canonical_title"] if row else "")
            conn.execute("UPDATE courses SET high_yield_points = ? WHERE id = ?", (json.dumps(bullets, ensure_ascii=False), cid))

    conn.commit()
    cov = conn.execute(
        """
        SELECT COUNT(*) FROM courses co
        WHERE co.canonical_title NOT IN ('Total :', 'Restant :', 'HPV')
          AND EXISTS (SELECT 1 FROM drive_files df WHERE df.course_id = co.id AND df.local_path IS NOT NULL)
        """
    ).fetchone()[0]
    print(f"Done. Linked docs={linked_count}, Courses with local docs={cov}/112")
    conn.close()


if __name__ == "__main__":
    main()
