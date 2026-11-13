"""FMPO 4-format grading helpers (QCM multi, QCM group, QROC/Synthesis rubric) & spaced repetition."""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any


def normalize_text(text: str) -> str:
    s = unicodedata.normalize("NFKD", text or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower()
    s = re.sub(r"[^a-z0-9%<>.,/+-]+", " ", s)
    return s.strip()


def grade_qcm(user_answers: list[str], correct_answers: list[str], question_type: str) -> dict[str, Any]:
    """Grade both qcm_group (single-choice) and qcm_multi (tout-ou-rien + partial score)."""
    u_set = {a.strip().upper() for a in user_answers if a.strip()}
    c_set = {a.strip().upper() for a in correct_answers if a.strip()}

    if not c_set:
        return {
            "is_correct": False,
            "partial_score": 0.0,
            "max_score": 1.0,
            "grading_note": "Clé non encore vérifiée pour cette question — utilisez la vérification ou l'annotation manuelle.",
        }

    if question_type == "qcm_group":
        ok = u_set == c_set
        return {
            "is_correct": ok,
            "partial_score": 1.0 if ok else 0.0,
            "max_score": 1.0,
            "grading_note": "Réponse exacte au groupement." if ok else f"Groupement attendu : {', '.join(sorted(c_set))}",
        }

    # qcm_multi: FMPO standard tout-ou-rien OR partial clinical Discordance score
    exact = u_set == c_set
    if exact:
        partial = 1.0
    else:
        # Each discrepancy (false positive or false negative across 5 items) costs 0.4
        diff = len(u_set ^ c_set)
        partial = max(0.0, round(1.0 - 0.35 * diff, 2))
    return {
        "is_correct": exact,
        "partial_score": partial,
        "max_score": 1.0,
        "grading_note": "Tout juste (1/1 barème FMPO)" if exact else f"Écart de {len(u_set ^ c_set)} item(s) — Réponse attendue : {''.join(sorted(c_set))}",
    }


STOP_WORDS = {
    "de", "du", "des", "la", "le", "les", "et", "ou", "en", "un", "une", "au", "aux", "par",
    "pour", "avec", "sans", "dans", "sur", "sous", "chez", "cas", "d", "l", "si", "est", "sont",
    "plus", "moins", "tres", "qui", "que", "dont", "entre", "vers", "tous", "tout", "avant", "apres",
}


def _bullet_tokens(bullet: str) -> list[str]:
    words = [w for w in normalize_text(bullet).split() if len(w) >= 3 and w not in STOP_WORDS]
    return words[:6]


def grade_qroc(user_text: str, rubric_points: list[str]) -> dict[str, Any]:
    """Compare written QROC response against expected medical key points."""
    norm_u = normalize_text(user_text)
    if not rubric_points:
        ok = len(norm_u) >= 12
        return {
            "is_correct": ok,
            "partial_score": 1.0 if ok else 0.0,
            "max_score": 1.0,
            "matched_points": [],
            "missed_points": [],
            "grading_note": "Auto-évaluation par rapport à la correction type.",
        }

    matched: list[str] = []
    missed: list[str] = []
    for pt in rubric_points:
        toks = _bullet_tokens(pt)
        if not toks:
            matched.append(pt)
            continue
        hits = sum(1 for t in toks if t in norm_u)
        ratio = hits / len(toks)
        if ratio >= 0.4 or any(len(t) >= 6 and t in norm_u for t in toks):
            matched.append(pt)
        else:
            missed.append(pt)

    score = round(len(matched) / max(1, len(rubric_points)), 2)
    return {
        "is_correct": score >= 0.65,
        "partial_score": score,
        "max_score": 1.0,
        "matched_points": matched,
        "missed_points": missed,
        "grading_note": f"{len(matched)}/{len(rubric_points)} notions clés retrouvées ({int(score * 100)}%).",
    }


def compute_next_review(rating: str, prev_mastery: float, reps: int, lapses: int) -> dict[str, Any]:
    """Simple SM-2/FSRS-inspired scheduling for medical course & concept mastery."""
    rating = rating.lower()
    now = datetime.now(timezone.utc)
    if rating == "again":
        new_mastery = max(10.0, prev_mastery * 0.5)
        days = 1
        new_reps = reps + 1
        new_lapses = lapses + 1
    elif rating == "hard":
        new_mastery = min(100.0, max(35.0, prev_mastery + 10.0))
        days = 2 if reps < 2 else 4
        new_reps = reps + 1
        new_lapses = lapses
    elif rating == "good":
        new_mastery = min(100.0, max(60.0, prev_mastery + 22.0))
        days = 1 if reps == 0 else (3 if reps == 1 else min(21, reps * 4))
        new_reps = reps + 1
        new_lapses = lapses
    else:  # easy
        new_mastery = min(100.0, max(80.0, prev_mastery + 32.0))
        days = 4 if reps == 0 else min(30, (reps + 1) * 6)
        new_reps = reps + 1
        new_lapses = lapses

    next_dt = (now + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    return {
        "mastery_score": round(new_mastery, 1),
        "reps": new_reps,
        "lapses": new_lapses,
        "last_reviewed_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "next_review_at": next_dt,
        "interval_days": days,
    }
