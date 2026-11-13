"""FastAPI backend for the S7 FMPO Study, Exam Simulator, Clinical Situations & Scan Digitizer Platform."""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import secrets
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.db import DATA_DIR, DB_PATH, get_conn, init_db, rows_to_dicts  # noqa: E402
from backend.grading import compute_next_review, grade_qcm, grade_qroc  # noqa: E402
from pipeline.ocr_scanner import digitize_image_page, render_pdf_pages  # noqa: E402

SCANS_DIR = DATA_DIR / "scans"
CACHE_BY_ID = DATA_DIR / "drive_cache" / "by_id"
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"

init_db(DB_PATH)

app = FastAPI(title="FMPO S7 MedPrep Studio", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def optional_basic_auth(request: Request, call_next):
    """Enforce HTTP Basic Auth on cloud deploys when APP_ACCESS_PASSWORD is set."""
    expected_pw = os.environ.get("APP_ACCESS_PASSWORD", "")
    if not expected_pw or request.url.path == "/api/health":
        return await call_next(request)

    expected_user = os.environ.get("APP_ACCESS_USER", "medprep")
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Basic "):
        try:
            decoded = base64.b64decode(auth_header[6:].strip()).decode("utf-8")
            user, _, pw = decoded.partition(":")
            if secrets.compare_digest(user, expected_user) and secrets.compare_digest(pw, expected_pw):
                return await call_next(request)
        except Exception:
            pass

    return Response(
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="FMPO S7 MedPrep Studio"'},
        content="Authentification requise",
    )


def _ensure_drive_file_local(conn, file_id: str) -> Path:
    row = conn.execute("SELECT id, name, local_path FROM drive_files WHERE id = ?", (file_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Fichier Drive introuvable")
    if row["local_path"]:
        lp = DATA_DIR / row["local_path"]
        if lp.exists():
            return lp

    dest = CACHE_BY_ID / file_id / row["name"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        res = subprocess.run(
            ["gdrive", "readonly", "download", file_id, "--out", str(tmp)],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="Téléchargement Drive à la demande indisponible sans le CLI gdrive local.",
        ) from exc
    if res.returncode != 0 or not tmp.exists():
        raise HTTPException(status_code=502, detail=f"Échec téléchargement Drive : {res.stderr.strip()}")
    tmp.rename(dest)
    rel = str(dest.relative_to(DATA_DIR))
    conn.execute("UPDATE drive_files SET local_path = ? WHERE id = ?", (rel, file_id))
    conn.commit()
    return dest


# --- Health & Dashboard ---

@app.get("/api/health")
def health() -> dict[str, Any]:
    conn = get_conn()
    try:
        return {
            "status": "ok",
            "modules": conn.execute("SELECT COUNT(*) FROM modules").fetchone()[0],
            "courses": conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0],
            "questions": conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0],
            "clinical_cases": conn.execute("SELECT COUNT(*) FROM clinical_cases").fetchone()[0],
            "drive_files": conn.execute("SELECT COUNT(*) FROM drive_files").fetchone()[0],
        }
    finally:
        conn.close()


@app.get("/api/dashboard")
def get_dashboard() -> dict[str, Any]:
    conn = get_conn()
    try:
        modules = rows_to_dicts(conn.execute("SELECT * FROM modules ORDER BY id").fetchall(), ("sub_disciplines",))
        mod_stats = []
        for m in modules:
            mid = m["id"]
            q_cnt = conn.execute("SELECT COUNT(*) FROM questions WHERE module_id = ? AND COALESCE(is_predicted, 0) = 0", (mid,)).fetchone()[0]
            c_cnt = conn.execute("SELECT COUNT(*) FROM courses WHERE module_id = ?", (mid,)).fetchone()[0]
            mastery_avg = conn.execute("SELECT COALESCE(AVG(mastery_score), 0) FROM courses WHERE module_id = ?", (mid,)).fetchone()[0]
            att = conn.execute(
                """
                SELECT COUNT(*) as total, COALESCE(SUM(is_correct), 0) as hits
                FROM question_attempts qa JOIN questions q ON qa.question_id = q.id
                WHERE q.module_id = ? AND COALESCE(q.is_predicted, 0) = 0
                """,
                (mid,),
            ).fetchone()
            sn_cnt = conn.execute("SELECT COUNT(*) FROM questions WHERE module_id = ? AND session = 'SN'", (mid,)).fetchone()[0]
            cases_cnt = conn.execute("SELECT COUNT(*) FROM clinical_cases WHERE module_id = ? AND COALESCE(is_predicted, 0) = 0", (mid,)).fetchone()[0]
            mod_stats.append({
                **m,
                "question_count": q_cnt,
                "sn2025_count": sn_cnt,
                "course_count": c_cnt,
                "clinical_cases_count": cases_cnt,
                "course_mastery_avg": round(mastery_avg, 1),
                "attempts_total": att["total"],
                "attempts_accuracy": round((att["hits"] / att["total"]) * 100, 1) if att["total"] else None,
            })

        total_q = conn.execute("SELECT COUNT(*) FROM questions WHERE COALESCE(is_predicted, 0) = 0").fetchone()[0]
        verified_q = conn.execute("SELECT COUNT(*) FROM questions WHERE COALESCE(is_predicted, 0) = 0 AND (json_array_length(correct_answers_json) > 0 OR question_type IN ('qroc', 'synthesis'))").fetchone()[0]
        sn_q = conn.execute("SELECT COUNT(*) FROM questions WHERE session = 'SN'").fetchone()[0]
        mistakes_flagged = conn.execute("SELECT COUNT(*) FROM questions WHERE verification_status = 'student_mistake_flagged'").fetchone()[0]
        total_attempts = conn.execute("SELECT COUNT(*) FROM question_attempts qa JOIN questions q ON qa.question_id = q.id WHERE COALESCE(q.is_predicted, 0) = 0").fetchone()[0]
        correct_attempts = conn.execute("SELECT COALESCE(SUM(qa.is_correct), 0) FROM question_attempts qa JOIN questions q ON qa.question_id = q.id WHERE COALESCE(q.is_predicted, 0) = 0").fetchone()[0]
        cases_completed = conn.execute("SELECT COUNT(DISTINCT cca.case_id) FROM clinical_case_attempts cca JOIN clinical_cases cc ON cca.case_id = cc.id WHERE COALESCE(cc.is_predicted, 0) = 0").fetchone()[0]
        total_cases = conn.execute("SELECT COUNT(*) FROM clinical_cases WHERE COALESCE(is_predicted, 0) = 0").fetchone()[0]
        possible_q_cnt = conn.execute("SELECT COUNT(*) FROM questions WHERE COALESCE(is_predicted, 0) = 1").fetchone()[0]
        possible_cases_cnt = conn.execute("SELECT COUNT(*) FROM clinical_cases WHERE COALESCE(is_predicted, 0) = 1").fetchone()[0]

        due_courses = rows_to_dicts(
            conn.execute(
                """
                SELECT id, module_id, sub_discipline, professor, canonical_title, upload_flag, mastery_score, exam_frequency
                FROM courses
                WHERE next_review_at IS NULL OR next_review_at <= datetime('now')
                ORDER BY CASE WHEN exam_frequency = 'high_yield' THEN 0 ELSE 1 END, mastery_score ASC, row_order ASC
                LIMIT 8
                """
            ).fetchall()
        )
        curriculum_alerts = rows_to_dicts(
            conn.execute(
                """
                SELECT id, module_id, sub_discipline, professor, canonical_title, upload_flag, promo_status
                FROM courses
                WHERE upload_flag IN ('nv_support_missing', 'sans_support')
                ORDER BY row_order ASC
                """
            ).fetchall()
        )
        return {
            "summary": {
                "total_questions": total_q,
                "ready_questions": verified_q,
                "sn2025_questions": sn_q,
                "sn2025_traps": mistakes_flagged,
                "total_courses": conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0],
                "total_attempts": total_attempts,
                "overall_accuracy": round((correct_attempts / total_attempts) * 100, 1) if total_attempts else 0.0,
                "cases_completed": cases_completed,
                "total_cases": total_cases,
                "possible_questions": possible_q_cnt,
                "possible_cases": possible_cases_cnt,
            },
            "modules": mod_stats,
            "due_courses": due_courses,
            "curriculum_alerts": curriculum_alerts,
        }
    finally:
        conn.close()


# --- Courses & Knowledge Hub ---

@app.get("/api/courses")
def list_courses(
    module_id: str | None = None,
    upload_flag: str | None = None,
    high_yield_only: bool = False,
    q: str | None = None,
) -> dict[str, Any]:
    conn = get_conn()
    try:
        sql = """
            SELECT c.*,
              (SELECT COUNT(*) FROM drive_files df WHERE df.course_id = c.id AND df.category = 'cours') as file_count,
              (SELECT COUNT(*) FROM drive_files df WHERE df.course_id = c.id AND df.category = 'resume_mohamed') as summary_count,
              (SELECT COUNT(*) FROM questions qn WHERE qn.course_id = c.id AND COALESCE(qn.is_predicted, 0) = 0) as question_count,
              (SELECT COUNT(*) FROM questions qn WHERE qn.course_id = c.id AND COALESCE(qn.is_predicted, 0) = 1) as predicted_count
            FROM courses c WHERE 1=1
        """
        params: list[Any] = []
        if module_id and module_id != "all":
            sql += " AND c.module_id = ?"
            params.append(module_id)
        if upload_flag and upload_flag != "all":
            sql += " AND c.upload_flag = ?"
            params.append(upload_flag)
        if high_yield_only:
            sql += " AND c.exam_frequency = 'high_yield'"
        if q:
            like = f"%{q.strip()}%"
            sql += " AND (c.canonical_title LIKE ? OR c.professor LIKE ? OR c.sub_discipline LIKE ?)"
            params.extend([like, like, like])
        sql += " ORDER BY c.row_order ASC"
        rows = rows_to_dicts(conn.execute(sql, params).fetchall(), ("high_yield_points",))
        return {"courses": rows, "count": len(rows)}
    finally:
        conn.close()


@app.get("/api/courses/{course_id}")
def get_course_detail(course_id: int) -> dict[str, Any]:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Cours introuvable")
        course = rows_to_dicts([row], ("high_yield_points",))[0]

        files = rows_to_dicts(
            conn.execute(
                "SELECT id, name, path, size, category, local_path, text_chars, page_count, is_scanned, version_tag FROM drive_files WHERE course_id = ? ORDER BY category ASC, name ASC",
                (course_id,),
            ).fetchall()
        )
        # Fallback prof files if none matched directly (e.g. sans_support / empty folder prof)
        if not files:
            prof_last = course["professor"].split()[-1] if course["professor"] else ""
            if len(prof_last) >= 3:
                files = rows_to_dicts(
                    conn.execute(
                        "SELECT id, name, path, size, category, local_path, text_chars, page_count, is_scanned, version_tag FROM drive_files WHERE module_id = ? AND professor LIKE ? ORDER BY category, name LIMIT 12",
                        (course["module_id"], f"%{prof_last}%"),
                    ).fetchall()
                )

        linked_qs = rows_to_dicts(
            conn.execute(
                """
                SELECT id, source_label, session, question_type, stem, statements_json, options_json,
                       correct_answers_json, rubric_json, explanation, verification_status, scan_page_image,
                       COALESCE(is_predicted, 0) as is_predicted, difficulty_tier, likelihood_score, doc_evidence
                FROM questions WHERE course_id = ? AND COALESCE(is_predicted, 0) = 0
                ORDER BY CASE WHEN session='SN' THEN 0 ELSE 1 END, id LIMIT 25
                """,
                (course_id,),
            ).fetchall(),
            ("statements_json", "options_json", "correct_answers_json", "rubric_json"),
        )
        predicted_qs = rows_to_dicts(
            conn.execute(
                """
                SELECT id, source_label, session, question_type, stem, statements_json, options_json,
                       correct_answers_json, rubric_json, explanation, verification_status, scan_page_image,
                       COALESCE(is_predicted, 0) as is_predicted, difficulty_tier, likelihood_score, doc_evidence
                FROM questions WHERE course_id = ? AND COALESCE(is_predicted, 0) = 1
                ORDER BY likelihood_score DESC, id LIMIT 20
                """,
                (course_id,),
            ).fetchall(),
            ("statements_json", "options_json", "correct_answers_json", "rubric_json"),
        )
        linked_cases = rows_to_dicts(
            conn.execute("SELECT id, slug, title, difficulty, source_tag, COALESCE(is_predicted, 0) as is_predicted FROM clinical_cases WHERE course_id = ?", (course_id,)).fetchall()
        )
        return {
            "course": course,
            "files": files,
            "questions": linked_qs,
            "predicted_questions": predicted_qs,
            "clinical_cases": linked_cases,
        }
    finally:
        conn.close()


class CourseReviewBody(BaseModel):
    rating: str  # again | hard | good | easy
    notes_markdown: str | None = None


@app.post("/api/courses/{course_id}/review")
def review_course(course_id: int, body: CourseReviewBody) -> dict[str, Any]:
    conn = get_conn()
    try:
        row = conn.execute("SELECT mastery_score, reps, lapses, notes_markdown FROM courses WHERE id = ?", (course_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Cours introuvable")
        sched = compute_next_review(body.rating, row["mastery_score"], row["reps"], row["lapses"])
        notes = body.notes_markdown if body.notes_markdown is not None else row["notes_markdown"]
        conn.execute(
            """
            UPDATE courses
            SET mastery_score = ?, reps = ?, lapses = ?, last_reviewed_at = ?, next_review_at = ?, notes_markdown = ?
            WHERE id = ?
            """,
            (
                sched["mastery_score"],
                sched["reps"],
                sched["lapses"],
                sched["last_reviewed_at"],
                sched["next_review_at"],
                notes,
                course_id,
            ),
        )
        conn.commit()
        return {"ok": True, **sched}
    finally:
        conn.close()


@app.get("/api/files/{file_id}/view")
def view_drive_file(file_id: str):
    conn = get_conn()
    try:
        local_p = _ensure_drive_file_local(conn, file_id)
        mime, _ = mimetypes.guess_type(local_p.name)
        headers = {"Content-Disposition": f'inline; filename="{local_p.name}"'}
        return FileResponse(str(local_p), media_type=mime or "application/octet-stream", headers=headers)
    finally:
        conn.close()


@app.get("/api/files/{file_id}/pages")
def render_file_pages(file_id: str) -> dict[str, Any]:
    """Return page count and single-page image URLs for instant lazy rendering."""
    conn = get_conn()
    try:
        df = conn.execute("SELECT name, page_count FROM drive_files WHERE id = ?", (file_id,)).fetchone()
        if not df:
            raise HTTPException(status_code=404, detail="Fichier introuvable")
        local_p = _ensure_drive_file_local(conn, file_id)
        if local_p.suffix.lower() != ".pdf":
            raise HTTPException(status_code=400, detail="Prévisualisation image réservée aux PDF")
        page_count = df["page_count"] or 0
        if page_count <= 0:
            import pypdf
            page_count = len(pypdf.PdfReader(str(local_p)).pages)
            conn.execute("UPDATE drive_files SET page_count = ? WHERE id = ?", (page_count, file_id))
            conn.commit()
        urls = [f"/api/files/{file_id}/page/{i}" for i in range(1, page_count + 1)]
        return {"file_id": file_id, "name": local_p.name, "page_count": page_count, "pages": urls}
    finally:
        conn.close()


@app.get("/api/files/{file_id}/page/{page_num}")
def render_single_file_page(file_id: str, page_num: int):
    """Render and cache a single PDF page cleanly on demand (~150ms)."""
    if page_num < 1:
        raise HTTPException(status_code=400, detail="Numéro de page invalide")
    conn = get_conn()
    try:
        local_p = _ensure_drive_file_local(conn, file_id)
    finally:
        conn.close()
    out_dir = SCANS_DIR / "preview" / file_id
    out_dir.mkdir(parents=True, exist_ok=True)
    cached = out_dir / f"single-{page_num}.png"
    if not cached.exists():
        prefix = out_dir / f"single-{page_num}"
        subprocess.run(
            ["pdftoppm", "-png", "-r", "115", "-f", str(page_num), "-l", str(page_num), "-singlefile", str(local_p), str(prefix)],
            check=True,
            capture_output=True,
        )
    if not cached.exists():
        raise HTTPException(status_code=404, detail="Page introuvable")
    return FileResponse(str(cached), media_type="image/png")


# --- Questions, Exam Simulator & Q-Bank ---

@app.get("/api/questions/sources")
def list_question_sources() -> dict[str, Any]:
    conn = get_conn()
    try:
        sources = rows_to_dicts(
            conn.execute(
                """
                SELECT source_label, module_id, session,
                       COUNT(*) as total,
                       SUM(CASE WHEN verification_status = 'student_mistake_flagged' THEN 1 ELSE 0 END) as traps
                FROM questions
                WHERE COALESCE(is_predicted, 0) = 0
                GROUP BY source_label, module_id, session
                ORDER BY CASE WHEN session='SN' THEN 0 WHEN session='Blanc' THEN 1 ELSE 2 END, source_label
                """
            ).fetchall()
        )
        return {"sources": sources}
    finally:
        conn.close()


@app.get("/api/questions")
def list_questions(
    module_id: str | None = None,
    sub_discipline: str | None = None,
    course_id: int | None = None,
    source_label: str | None = None,
    session: str | None = None,
    question_type: str | None = None,
    traps_only: bool = False,
    unanswered_only: bool = False,
    verified_only: bool = False,
    predicted: str = "exclude",
    q: str | None = None,
    shuffle: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    conn = get_conn()
    try:
        where = ["1=1"]
        params: list[Any] = []
        if predicted == "exclude":
            where.append("COALESCE(qn.is_predicted, 0) = 0")
        elif predicted == "only":
            where.append("COALESCE(qn.is_predicted, 0) = 1")
        if module_id and module_id != "all":
            where.append("qn.module_id = ?")
            params.append(module_id)
        if sub_discipline and sub_discipline != "all":
            where.append("qn.sub_discipline = ?")
            params.append(sub_discipline)
        if course_id:
            where.append("qn.course_id = ?")
            params.append(course_id)
        if source_label and source_label != "all":
            where.append("qn.source_label = ?")
            params.append(source_label)
        if session and session != "all":
            where.append("qn.session = ?")
            params.append(session)
        if question_type and question_type != "all":
            where.append("qn.question_type = ?")
            params.append(question_type)
        if traps_only:
            where.append("qn.verification_status = 'student_mistake_flagged'")
        if verified_only:
            where.append("(json_array_length(qn.correct_answers_json) > 0 OR qn.question_type IN ('qroc', 'synthesis'))")
        if unanswered_only:
            where.append("NOT EXISTS (SELECT 1 FROM question_attempts qa WHERE qa.question_id = qn.id)")
        if q:
            like = f"%{q.strip()}%"
            where.append("(qn.stem LIKE ? OR qn.vignette_text LIKE ? OR qn.explanation LIKE ?)")
            params.extend([like, like, like])

        where_sql = " AND ".join(where)
        total = conn.execute(f"SELECT COUNT(*) FROM questions qn WHERE {where_sql}", params).fetchone()[0]
        order = "RANDOM()" if shuffle else "CASE WHEN qn.session='SN' THEN 0 WHEN qn.session='Blanc' THEN 1 ELSE 2 END, qn.question_number ASC, qn.id ASC"
        rows = conn.execute(
            f"""
            SELECT qn.*, c.canonical_title as course_title
            FROM questions qn LEFT JOIN courses c ON qn.course_id = c.id
            WHERE {where_sql}
            ORDER BY {order}
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset],
        ).fetchall()
        qs = rows_to_dicts(rows, ("statements_json", "options_json", "correct_answers_json", "rubric_json"))
        return {"questions": qs, "total": total}
    finally:
        conn.close()


class AttemptBody(BaseModel):
    session_id: str = "practice"
    mode: str = "qcm"
    selected_answers: list[str] = []
    written_answer: str = ""
    confidence: str | None = None


@app.post("/api/questions/{question_id}/attempt")
def submit_question_attempt(question_id: int, body: AttemptBody) -> dict[str, Any]:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Question introuvable")
        q = rows_to_dicts([row], ("statements_json", "options_json", "correct_answers_json", "rubric_json"))[0]

        if q["question_type"] in ("qroc", "synthesis"):
            rubric_pts = q["rubric_json"].get("points", []) if isinstance(q["rubric_json"], dict) else []
            res = grade_qroc(body.written_answer, rubric_pts)
            ans_store = json.dumps({"written_answer": body.written_answer}, ensure_ascii=False)
        else:
            res = grade_qcm(body.selected_answers, q["correct_answers_json"], q["question_type"])
            ans_store = json.dumps(body.selected_answers, ensure_ascii=False)

        conn.execute(
            """
            INSERT INTO question_attempts (question_id, session_id, mode, user_answer_json, is_correct, partial_score, max_score, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                question_id,
                body.session_id,
                body.mode,
                ans_store,
                1 if res["is_correct"] else 0,
                res["partial_score"],
                res["max_score"],
                body.confidence,
            ),
        )
        # Update course mastery slightly on live attempt
        if q.get("course_id"):
            delta = 4.0 if res["is_correct"] else -1.5
            conn.execute(
                "UPDATE courses SET mastery_score = MIN(100.0, MAX(0.0, mastery_score + ?)) WHERE id = ?",
                (delta, q["course_id"]),
            )
        conn.commit()
        return {
            **res,
            "correct_answers": q["correct_answers_json"],
            "rubric": q["rubric_json"],
            "explanation": q["explanation"],
            "verification_status": q["verification_status"],
            "scan_page_image": q["scan_page_image"],
            "is_predicted": bool(q["is_predicted"]) if "is_predicted" in q else False,
            "difficulty_tier": q.get("difficulty_tier", "standard"),
            "likelihood_score": q.get("likelihood_score", 75),
            "doc_evidence": q.get("doc_evidence", ""),
        }
    finally:
        conn.close()


# --- Annales & Strike Radar ---

@app.get("/api/analytics/radar")
def get_radar() -> dict[str, Any]:
    conn = get_conn()
    try:
        by_bank = rows_to_dicts(
            conn.execute(
                """
                SELECT q.source_label, q.module_id, q.session,
                       COUNT(*) as question_count,
                       SUM(CASE WHEN json_array_length(q.correct_answers_json) > 0 OR q.question_type IN ('qroc','synthesis') THEN 1 ELSE 0 END) as keyed_count,
                       SUM(CASE WHEN q.verification_status = 'student_mistake_flagged' THEN 1 ELSE 0 END) as trap_count,
                       (SELECT COUNT(*) FROM question_attempts qa JOIN questions q2 ON qa.question_id = q2.id WHERE q2.source_label = q.source_label) as attempts,
                       (SELECT COALESCE(SUM(qa.is_correct),0) FROM question_attempts qa JOIN questions q2 ON qa.question_id = q2.id WHERE q2.source_label = q.source_label) as hits
                FROM questions q
                WHERE COALESCE(q.is_predicted, 0) = 0
                GROUP BY q.source_label, q.module_id, q.session
                ORDER BY CASE WHEN q.session='SN' THEN 0 WHEN q.session='Blanc' THEN 1 ELSE 2 END, question_count DESC
                """
            ).fetchall()
        )
        hot_courses = rows_to_dicts(
            conn.execute(
                """
                SELECT c.id, c.module_id, c.sub_discipline, c.professor, c.canonical_title, c.upload_flag, c.mastery_score,
                       COUNT(q.id) as q_count,
                       SUM(CASE WHEN q.session = 'SN' THEN 1 ELSE 0 END) as sn_count
                FROM courses c
                JOIN questions q ON q.course_id = c.id
                WHERE COALESCE(q.is_predicted, 0) = 0
                GROUP BY c.id
                ORDER BY sn_count DESC, q_count DESC
                LIMIT 20
                """
            ).fetchall()
        )
        sn_traps = rows_to_dicts(
            conn.execute(
                """
                SELECT id, module_id, sub_discipline, source_label, question_number, stem, correct_answers_json, explanation, scan_page_image
                FROM questions
                WHERE verification_status = 'student_mistake_flagged'
                ORDER BY module_id, question_number
                """
            ).fetchall(),
            ("correct_answers_json",),
        )
        return {"banks": by_bank, "hot_courses": hot_courses, "sn2025_traps": sn_traps}
    finally:
        conn.close()


# --- Clinical Situations Simulator ---

@app.get("/api/clinical-cases")
def list_clinical_cases(module_id: str | None = None, predicted: str = "exclude") -> dict[str, Any]:
    conn = get_conn()
    try:
        where = ["1=1"]
        params: list[Any] = []
        if predicted == "exclude":
            where.append("COALESCE(cc.is_predicted, 0) = 0")
        elif predicted == "only":
            where.append("COALESCE(cc.is_predicted, 0) = 1")
        if module_id and module_id != "all":
            where.append("cc.module_id = ?")
            params.append(module_id)
        sql = f"""
            SELECT cc.*, c.canonical_title as course_title,
                   (SELECT MAX(score * 1.0 / NULLIF(max_score, 0)) FROM clinical_case_attempts cca WHERE cca.case_id = cc.id) as best_ratio,
                   (SELECT COUNT(*) FROM clinical_case_attempts cca WHERE cca.case_id = cc.id) as attempt_count
            FROM clinical_cases cc LEFT JOIN courses c ON cc.course_id = c.id
            WHERE {' AND '.join(where)}
            ORDER BY cc.id ASC
        """
        cases = rows_to_dicts(conn.execute(sql, params).fetchall(), ("vitals_json", "steps_json", "takeaway_points"))
        return {"cases": cases}
    finally:
        conn.close()


@app.get("/api/possible-questions")
def get_possible_questions(
    module_id: str | None = None,
    course_id: int | None = None,
    difficulty_tier: str | None = None,
    question_type: str | None = None,
    zero_annale_only: bool = False,
    q: str | None = None,
    limit: int = Query(150, ge=1, le=400),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """Return high-yield AI-predicted exam questions & complex multi-step clinical cases mined from all S7 docs."""
    conn = get_conn()
    try:
        total_pred_q = conn.execute("SELECT COUNT(*) FROM questions WHERE COALESCE(is_predicted, 0) = 1").fetchone()[0]
        total_pred_cases = conn.execute("SELECT COUNT(*) FROM clinical_cases WHERE COALESCE(is_predicted, 0) = 1").fetchone()[0]
        piege_jury_cnt = conn.execute("SELECT COUNT(*) FROM questions WHERE COALESCE(is_predicted, 0) = 1 AND difficulty_tier = 'piege_jury'").fetchone()[0]
        docs_analyzed = conn.execute("SELECT COUNT(*) FROM drive_files WHERE category IN ('cours', 'resume_mohamed') AND local_path IS NOT NULL").fetchone()[0]

        zero_annale_q = conn.execute(
            """
            SELECT COUNT(*) FROM questions qn
            WHERE COALESCE(qn.is_predicted, 0) = 1
              AND NOT EXISTS (SELECT 1 FROM questions a WHERE a.course_id = qn.course_id AND COALESCE(a.is_predicted, 0) = 0)
            """
        ).fetchone()[0]

        by_mod = rows_to_dicts(
            conn.execute(
                """
                SELECT m.id as module_id, m.short_name, m.name,
                       (SELECT COUNT(*) FROM questions qn WHERE qn.module_id = m.id AND COALESCE(qn.is_predicted, 0) = 1) as q_count,
                       (SELECT COUNT(*) FROM clinical_cases cc WHERE cc.module_id = m.id AND COALESCE(cc.is_predicted, 0) = 1) as case_count
                FROM modules m
                ORDER BY m.id
                """
            ).fetchall()
        )

        pred_courses = rows_to_dicts(
            conn.execute(
                """
                SELECT co.id, co.module_id, co.sub_discipline, co.professor, co.canonical_title, co.promo_status,
                       (SELECT COUNT(*) FROM questions a WHERE a.course_id = co.id AND COALESCE(a.is_predicted, 0) = 0) as annale_cnt,
                       (SELECT COUNT(*) FROM questions pq WHERE pq.course_id = co.id AND COALESCE(pq.is_predicted, 0) = 1) as predicted_cnt,
                       (SELECT COUNT(*) FROM drive_files df WHERE df.course_id = co.id AND df.local_path IS NOT NULL) as doc_cnt
                FROM courses co
                WHERE EXISTS (SELECT 1 FROM questions pq WHERE pq.course_id = co.id AND COALESCE(pq.is_predicted, 0) = 1)
                ORDER BY co.module_id, annale_cnt ASC, co.row_order ASC
                """
            ).fetchall()
        )

        q_where = ["COALESCE(qn.is_predicted, 0) = 1"]
        q_params: list[Any] = []
        if module_id and module_id != "all":
            q_where.append("qn.module_id = ?")
            q_params.append(module_id)
        if course_id:
            q_where.append("qn.course_id = ?")
            q_params.append(course_id)
        if difficulty_tier and difficulty_tier != "all":
            q_where.append("qn.difficulty_tier = ?")
            q_params.append(difficulty_tier)
        if question_type and question_type != "all":
            q_where.append("qn.question_type = ?")
            q_params.append(question_type)
        if zero_annale_only:
            q_where.append("NOT EXISTS (SELECT 1 FROM questions a WHERE a.course_id = qn.course_id AND COALESCE(a.is_predicted, 0) = 0)")
        if q:
            like = f"%{q.strip()}%"
            q_where.append("(qn.stem LIKE ? OR qn.explanation LIKE ? OR qn.doc_evidence LIKE ? OR c.canonical_title LIKE ?)")
            q_params.extend([like, like, like, like])

        q_where_sql = " AND ".join(q_where)
        filtered_total = conn.execute(
            f"SELECT COUNT(*) FROM questions qn LEFT JOIN courses c ON qn.course_id = c.id WHERE {q_where_sql}",
            q_params,
        ).fetchone()[0]
        q_rows = conn.execute(
            f"""
            SELECT qn.*, c.canonical_title as course_title,
                   (SELECT COUNT(*) FROM questions a WHERE a.course_id = qn.course_id AND COALESCE(a.is_predicted, 0) = 0) as course_annale_cnt
            FROM questions qn
            LEFT JOIN courses c ON qn.course_id = c.id
            WHERE {q_where_sql}
            ORDER BY CASE WHEN qn.difficulty_tier = 'piege_jury' THEN 0 ELSE 1 END, qn.likelihood_score DESC, course_annale_cnt ASC, qn.id ASC
            LIMIT ? OFFSET ?
            """,
            q_params + [limit, offset],
        ).fetchall()
        questions = rows_to_dicts(q_rows, ("statements_json", "options_json", "correct_answers_json", "rubric_json"))

        c_where = ["COALESCE(cc.is_predicted, 0) = 1"]
        c_params: list[Any] = []
        if module_id and module_id != "all":
            c_where.append("cc.module_id = ?")
            c_params.append(module_id)
        if q:
            like = f"%{q.strip()}%"
            c_where.append("(cc.title LIKE ? OR cc.patient_summary LIKE ? OR cc.doc_evidence LIKE ?)")
            c_params.extend([like, like, like])
        cases = rows_to_dicts(
            conn.execute(
                f"""
                SELECT cc.*, c.canonical_title as course_title,
                       (SELECT MAX(score * 1.0 / NULLIF(max_score, 0)) FROM clinical_case_attempts cca WHERE cca.case_id = cc.id) as best_ratio,
                       (SELECT COUNT(*) FROM clinical_case_attempts cca WHERE cca.case_id = cc.id) as attempt_count
                FROM clinical_cases cc
                LEFT JOIN courses c ON cc.course_id = c.id
                WHERE {' AND '.join(c_where)}
                ORDER BY cc.module_id, cc.id ASC
                """,
                c_params,
            ).fetchall(),
            ("vitals_json", "steps_json", "takeaway_points"),
        )

        return {
            "summary": {
                "total_questions": total_pred_q,
                "filtered_questions": filtered_total,
                "total_cases": total_pred_cases,
                "piege_jury_count": piege_jury_cnt,
                "zero_annale_questions": zero_annale_q,
                "docs_analyzed": docs_analyzed,
                "doc_backed_courses": len(pred_courses),
            },
            "by_module": by_mod,
            "courses": pred_courses,
            "questions": questions,
            "cases": cases,
        }
    finally:
        conn.close()


@app.get("/api/clinical-cases/{slug}")
def get_clinical_case(slug: str) -> dict[str, Any]:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT cc.*, c.canonical_title as course_title FROM clinical_cases cc LEFT JOIN courses c ON cc.course_id = c.id WHERE cc.slug = ?",
            (slug,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Situation clinique introuvable")
        return {"case": rows_to_dicts([row], ("vitals_json", "steps_json", "takeaway_points"))[0]}
    finally:
        conn.close()


class CaseAttemptBody(BaseModel):
    score: float
    max_score: float
    answers: dict[str, Any] = {}


@app.post("/api/clinical-cases/{case_id}/attempt")
def record_case_attempt(case_id: int, body: CaseAttemptBody) -> dict[str, Any]:
    conn = get_conn()
    try:
        row = conn.execute("SELECT course_id FROM clinical_cases WHERE id = ?", (case_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Situation clinique introuvable")
        conn.execute(
            "INSERT INTO clinical_case_attempts (case_id, score, max_score, answers_json) VALUES (?, ?, ?, ?)",
            (case_id, body.score, body.max_score, json.dumps(body.answers, ensure_ascii=False)),
        )
        if row["course_id"]:
            ratio = body.score / max(1.0, body.max_score)
            bonus = 12.0 if ratio >= 0.7 else 4.0
            conn.execute(
                "UPDATE courses SET mastery_score = MIN(100.0, mastery_score + ?) WHERE id = ?",
                (bonus, row["course_id"]),
            )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


# --- Scan & Corrigé Digitizer Studio ---

@app.get("/api/scans/catalog")
def scan_catalog() -> dict[str, Any]:
    conn = get_conn()
    try:
        drive_scans = rows_to_dicts(
            conn.execute(
                """
                SELECT id, name, path, size, module_id, category, local_path, page_count, is_scanned, is_corrige
                FROM drive_files
                WHERE (is_scanned = 1 OR category IN ('examen_sn', 'corrige', 'non_corrige')) AND name LIKE '%.pdf'
                ORDER BY CASE WHEN category = 'examen_sn' THEN 0 WHEN is_corrige = 1 THEN 1 ELSE 2 END, name ASC
                """
            ).fetchall()
        )
        jobs = rows_to_dicts(conn.execute("SELECT * FROM scan_jobs ORDER BY created_at DESC").fetchall(), ("pages_json",))
        # Also include pre-digitized SN 2025 & scanned batches
        sn_pre = []
        for prefix, label, mod in [
            ("aps", "EXAMEN APS 2025 SN", "anapath"),
            ("endo", "EXAMEN ENDOCRINO 2025 SN", "endocrino-dermato"),
            ("derm", "EXAMEN DERMATO 2025 SN", "endocrino-dermato"),
            ("hemato", "EXAMEN HEMATO ONCO 2025 SN", "hemato-onco"),
            ("neuro", "EXAMEN NEURO NEUROCHIR 2025 SN", "neuro-neurochir"),
        ]:
            imgs = sorted((SCANS_DIR / "sn2025").glob(f"{prefix}-*.png"), key=lambda p: p.name)
            sn_pre.append({
                "job_id": f"sn2025_{prefix}",
                "label": label,
                "module_id": mod,
                "page_count": len(imgs),
                "pages": [f"/api/scans/sn2025/{p.name}" for p in imgs],
            })
        return {"drive_scans": drive_scans, "custom_jobs": jobs, "sn2025_batches": sn_pre}
    finally:
        conn.close()


@app.get("/api/scans/sn2025-pages/{prefix}")
def get_sn2025_batch(prefix: str) -> dict[str, Any]:
    conn = get_conn()
    try:
        imgs = sorted((SCANS_DIR / "sn2025").glob(f"{prefix}-*.png"), key=lambda p: p.name)
        if not imgs:
            raise HTTPException(status_code=404, detail="Lot introuvable")
        pages = []
        for im in imgs:
            url = f"/api/scans/sn2025/{im.name}"
            qs = rows_to_dicts(
                conn.execute(
                    "SELECT * FROM questions WHERE scan_page_image = ? ORDER BY question_number, id",
                    (url,),
                ).fetchall(),
                ("statements_json", "options_json", "correct_answers_json", "rubric_json"),
            )
            pages.append({"image": url, "filename": im.name, "questions": qs})
        return {"prefix": prefix, "pages": pages}
    finally:
        conn.close()


@app.post("/api/scans/prepare/{file_id}")
def prepare_drive_scan(file_id: str) -> dict[str, Any]:
    """Download from Drive if needed, render pages to PNG, and register a digitizer job."""
    conn = get_conn()
    try:
        df = conn.execute("SELECT id, name, module_id, is_corrige FROM drive_files WHERE id = ?", (file_id,)).fetchone()
        if not df:
            raise HTTPException(status_code=404, detail="Fichier introuvable")
        local_p = _ensure_drive_file_local(conn, file_id)
        job_dir = SCANS_DIR / "jobs" / file_id
        imgs = sorted(job_dir.glob("page-*.png"), key=lambda p: p.name)
        if not imgs:
            imgs = render_pdf_pages(local_p, job_dir, dpi=130, prefix="page")
        pages = [
            {
                "page_num": i + 1,
                "image": f"/api/scans/jobs/{file_id}/{p.name}",
                "cached_json": (job_dir / f"{p.stem}.json").exists(),
            }
            for i, p in enumerate(imgs)
        ]
        conn.execute(
            """
            INSERT INTO scan_jobs (id, source_file_id, filename, module_id, source_type, page_count, status, pages_json)
            VALUES (?, ?, ?, ?, ?, ?, 'ready', ?)
            ON CONFLICT(id) DO UPDATE SET page_count=excluded.page_count, pages_json=excluded.pages_json
            """,
            (
                file_id,
                file_id,
                df["name"],
                df["module_id"] or "anapath",
                "corrige" if df["is_corrige"] else "examen",
                len(pages),
                json.dumps(pages, ensure_ascii=False),
            ),
        )
        conn.commit()
        return {"job_id": file_id, "filename": df["name"], "module_id": df["module_id"], "pages": pages}
    finally:
        conn.close()


@app.post("/api/scans/upload")
async def upload_scan(
    file: UploadFile = File(...),
    module_id: str = Form("anapath"),
    source_type: str = Form("examen"),
) -> dict[str, Any]:
    job_id = f"up_{uuid.uuid4().hex[:10]}"
    job_dir = SCANS_DIR / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    raw_dest = job_dir / (file.filename or "scan.pdf")
    raw_dest.write_bytes(await file.read())

    if raw_dest.suffix.lower() == ".pdf":
        imgs = render_pdf_pages(raw_dest, job_dir, dpi=130, prefix="page")
    else:
        pg1 = job_dir / "page-01.png"
        shutil.copy2(raw_dest, pg1)
        imgs = [pg1]

    pages = [
        {"page_num": i + 1, "image": f"/api/scans/jobs/{job_id}/{p.name}", "cached_json": False}
        for i, p in enumerate(imgs)
    ]
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO scan_jobs (id, source_file_id, filename, module_id, source_type, page_count, status, pages_json)
            VALUES (?, NULL, ?, ?, ?, ?, 'ready', ?)
            """,
            (job_id, file.filename or "scan.pdf", module_id, source_type, len(pages), json.dumps(pages, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        conn.close()
    return {"job_id": job_id, "filename": file.filename, "module_id": module_id, "pages": pages}


@app.post("/api/scans/jobs/{job_id}/ocr/{page_num}")
def ocr_job_page(job_id: str, page_num: int, module_hint: str = Body("Médecine S7 FMPO", embed=True)) -> dict[str, Any]:
    job_dir = SCANS_DIR / "jobs" / job_id
    if not job_dir.exists():
        # Check sn2025 or extra dirs
        raise HTTPException(status_code=404, detail="Lot de numérisation introuvable")
    imgs = sorted(job_dir.glob("page-*.png"), key=lambda p: p.name)
    if page_num < 1 or page_num > len(imgs):
        raise HTTPException(status_code=404, detail="Numéro de page invalide")
    img_path = imgs[page_num - 1]
    json_path = job_dir / f"{img_path.stem}.json"
    if json_path.exists():
        data = json.loads(json_path.read_text(encoding="utf-8"))
    else:
        data = digitize_image_page(img_path, module_hint=module_hint)
        json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "job_id": job_id,
        "page_num": page_num,
        "image": f"/api/scans/jobs/{job_id}/{img_path.name}",
        "ocr": data,
    }


class SaveQuestionBody(BaseModel):
    question_id: int | None = None
    module_id: str
    sub_discipline: str
    source_label: str
    question_number: int | None = None
    question_type: str
    stem: str
    statements: list[dict[str, str]] = []
    options: list[dict[str, str]] = []
    correct_answers: list[str] = []
    rubric_points: list[str] = []
    explanation: str = ""
    scan_page_image: str | None = None
    verification_status: str = "verified_key"


@app.post("/api/scans/save-question")
def save_verified_question(body: SaveQuestionBody) -> dict[str, Any]:
    conn = get_conn()
    try:
        if body.question_id:
            conn.execute(
                """
                UPDATE questions
                SET stem = ?, statements_json = ?, options_json = ?, correct_answers_json = ?,
                    rubric_json = ?, explanation = ?, verification_status = ?
                WHERE id = ?
                """,
                (
                    body.stem,
                    json.dumps(body.statements, ensure_ascii=False),
                    json.dumps(body.options, ensure_ascii=False),
                    json.dumps(body.correct_answers, ensure_ascii=False),
                    json.dumps({"points": body.rubric_points}, ensure_ascii=False),
                    body.explanation,
                    body.verification_status,
                    body.question_id,
                ),
            )
            qid = body.question_id
        else:
            ext_key = f"manual_{uuid.uuid4().hex[:10]}"
            cur = conn.execute(
                """
                INSERT INTO questions (
                    external_key, module_id, sub_discipline, source_label, exam_year, session,
                    question_number, question_type, stem, statements_json, options_json,
                    correct_answers_json, rubric_json, explanation, verification_status, scan_page_image, frequency_tag
                ) VALUES (?, ?, ?, ?, '2026', 'Scan Studio', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'digitized')
                """,
                (
                    ext_key,
                    body.module_id,
                    body.sub_discipline,
                    body.source_label,
                    body.question_number or 1,
                    body.question_type,
                    body.stem,
                    json.dumps(body.statements, ensure_ascii=False),
                    json.dumps(body.options, ensure_ascii=False),
                    json.dumps(body.correct_answers, ensure_ascii=False),
                    json.dumps({"points": body.rubric_points}, ensure_ascii=False),
                    body.explanation,
                    body.verification_status,
                    body.scan_page_image,
                ),
            )
            qid = cur.lastrowid
        conn.commit()
        return {"ok": True, "question_id": qid}
    finally:
        conn.close()


@app.get("/api/scans/{subpath:path}")
def serve_scan_image(subpath: str):
    target = (SCANS_DIR / subpath).resolve()
    if not str(target).startswith(str(SCANS_DIR.resolve())) or not target.exists():
        raise HTTPException(status_code=404, detail="Image introuvable")
    return FileResponse(str(target), media_type="image/png")


# Serve built SPA if present
if FRONTEND_DIST.exists() and (FRONTEND_DIST / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        candidate = (FRONTEND_DIST / full_path).resolve()
        if candidate.is_file() and str(candidate).startswith(str(FRONTEND_DIST.resolve())):
            return FileResponse(str(candidate))
        return FileResponse(str(FRONTEND_DIST / "index.html"))
