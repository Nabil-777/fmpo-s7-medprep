#!/usr/bin/env python3
"""Scan & Corrigé digitization helpers using pdftoppm and Vision-LLM structured OCR."""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

MODELS = ["gemini-3-flash-preview", "gemini-3.1-flash-lite-preview", "gemini-3.1-pro-preview"]

PROMPT_TEMPLATE = """Tu es un expert en numérisation d'examens médicaux FMPO (Faculté de Médecine d'Oujda, 4e année S7, français).
Analyse cette image de page d'examen ou de corrigé annoté ({module_hint}) et extrais TOUTES les questions présentes sur la page en JSON STRICT (un objet `{{"page_header": "...", "questions": [...]}}`).

Règles strictes d'extraction :
1. Transcris le français EXACT sans résumer ni omettre de mots médicaux (stem, vignettes cliniques éventuelles, propositions `a, b, c, d, e` ou options `A, B, C, D, E...`).
2. Détermine `question_type` :
   - `"qcm_group"` si la question liste des propositions minuscules `a., b., c., d., e.` suivies de choix de regroupement majuscules `A(...), B(...), C(...), D(...), E(...)` (typique d'Anapath/APS). Dans ce cas, mets `a..e` dans `statements` et les choix `A..E` (avec leur texte exact ex: `a;b;c`) dans `options`.
   - `"qcm_multi"` pour les QCM classiques à choix multiples `A, B, C, D, E...`. Mets les options dans `options` et `statements: []`.
   - `"qroc"` ou `"synthesis"` pour les questions rédactionnelles (Neurologie / Neurochirurgie / synthèse de cours). Mets les puces de correction attendues dans `rubric_points` si visibles sur la page.
3. Lecture précise des annotations visuelles sur la page :
   - `marked_letters`: lettres entourées, surlignées en vert/jaune ou cochées.
   - `margin_correct_letters`: lettres écrites dans la marge droite ou à côté de la question (ex: `"ABE"`, `"D"`).
   - `student_mistake_flag`: `true` uniquement si un `X` rouge (ou croix d'erreur de notation) figure dans la marge gauche à côté du numéro de question, sinon `false`.
   - `handwritten_notes`: annotations manuscrites éventuelles en rouge/vert (ex: `"20%"`, `"basse"`, `"neuropathique"`).
   - `verified_correct_letters`: liste des lettres réellement justes médicalement selon le corrigé visible ET tes connaissances médicales exactes (ex: `["A", "C"]` ou `["E"]`). Si un `X` rouge montre que l'étudiant s'était trompé en entourant une lettre, corrige avec les bonnes lettres !
   - `explanation`: courte explication médicale en français (1-3 phrases) clarifiant pourquoi ces réponses sont justes (et signalant l'erreur s'il y avait un `X`).

Format JSON attendu uniquement (sans markdown ni texte autour) :
{{
  "page_header": "string",
  "questions": [
    {{
      "question_number": 1,
      "vignette_text": null,
      "question_type": "qcm_multi",
      "stem": "texte exact de la question",
      "statements": [{{"letter": "a", "text": "..."}}],
      "options": [{{"letter": "A", "text": "..."}}],
      "marked_letters": ["A", "B"],
      "margin_correct_letters": ["A", "B"],
      "student_mistake_flag": false,
      "handwritten_notes": "",
      "verified_correct_letters": ["A", "B"],
      "rubric_points": [],
      "explanation": "..."
    }}
  ]
}}
"""


def render_pdf_pages(pdf_path: Path, out_dir: Path, dpi: int = 140, prefix: str = "page") -> list[Path]:
    """Render PDF pages cleanly to PNG files using pdftoppm."""
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["pdftoppm", "-png", "-r", str(dpi), str(pdf_path), str(out_dir / prefix)],
        check=True,
        capture_output=True,
    )
    return sorted(out_dir.glob(f"{prefix}-*.png"), key=lambda p: p.name)


def _extract_json_block(text: str) -> dict[str, Any]:
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


def digitize_image_page(image_path: Path, module_hint: str = "Médecine S7 FMPO") -> dict[str, Any]:
    """Send a rendered exam/corrigé image to Vision-LLM and return structured JSON."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY non configurée dans l'environnement.")

    img_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    prompt = PROMPT_TEMPLATE.format(module_hint=module_hint)
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": "image/png", "data": img_b64}},
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }

    last_err: Exception | None = None
    for attempt in range(3):
        for model in MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=75) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    txt = body["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = _extract_json_block(txt)
                    parsed["model_used"] = model
                    return parsed
            except (urllib.error.HTTPError, urllib.error.URLError, KeyError, json.JSONDecodeError, TimeoutError) as exc:
                last_err = exc
                time.sleep(1.5)
                continue
        time.sleep(4 * (attempt + 1))
    raise RuntimeError(f"Échec OCR Vision pour {image_path.name}: {last_err}")
