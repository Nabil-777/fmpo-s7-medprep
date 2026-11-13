#!/usr/bin/env python3
"""Analyze all S7 course documents (text + scanned PDFs via Gemini Vision) and generate
hard exam-grade Possible Questions ('wa3ra' / 'piege_jury') and Complex Clinical Cases.
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.db import DATA_DIR, DB_PATH, get_conn, init_db  # noqa: E402
from pipeline.sync_missing_courses import extract_full_text  # noqa: E402

CACHE_PATH = DATA_DIR / "possible_questions_cache.json"
MODELS_QUESTIONS = [
    "gemini-3.6-flash",
    "gemini-4-hydrogen",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.1-flash-lite-preview",
    "gemini-flash-lite-latest",
]
MODELS_CASES = [
    "gemini-4-hydrogen",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
]
_MODEL_LOCK = threading.Lock()
_DEAD_MODELS: set[str] = set()
_COOLDOWN_UNTIL: dict[str, float] = {}

# Showcase clinical scenarios to synthesize from real course documents (complementing the 11 base cases)
COMPLEX_CASE_BLUEPRINTS: list[dict[str, Any]] = [
    # --- ANAPATH (6 complex dossiers from real uploaded docs) ---
    {"slug": "poss_anapath_gastrite_malt", "module_id": "anapath", "sub_discipline": "Anatomopathologie", "course_hints": ["gastrites", "lymphomes"], "focus": "Gastrite chronique à HP évoluant vers lymphome gastrique du MALT vs atrophie/métaplasie intestinale, biopsies Sydney/OLGA, IHC CD20/BCL2/t(11;18) et réponse à l'éradication."},
    {"slug": "poss_anapath_estomac_linitis", "module_id": "anapath", "sub_discipline": "Anatomopathologie", "course_hints": ["estomac"], "focus": "Adénocarcinome gastrique à cellules indépendantes en bague à chaton (linite) vs type intestinal de Lauren, curage ganglionnaire, statut HER2 et instabilité microsatellitaire (MSI)."},
    {"slug": "poss_anapath_poumon_molecular", "module_id": "anapath", "sub_discipline": "Anatomopathologie", "course_hints": ["poumon"], "focus": "Carcinome bronchique à petites cellules vs adénocarcinome vs carcinome épidermoïde (TTF-1, p40/p63, synaptophysine/chromogranine/Ki67), économie tissulaire et testing moléculaire EGFR/ALK/ROS1/PD-L1."},
    {"slug": "poss_anapath_rein_foie", "module_id": "anapath", "sub_discipline": "Anatomopathologie", "course_hints": ["rein"], "focus": "Tumeur rénale solide à cellules claires vs carcinome chromophobe vs oncocytome (grade ISUP/Fuhrman, VHL, Hale/CD117/PAX8/CAIX) et règles de la biopsie rénale / néphrectomie."},
    {"slug": "poss_anapath_mici_dysplasie", "module_id": "anapath", "sub_discipline": "Anatomopathologie", "course_hints": ["mici"], "focus": "Rectocolite hémorragique vs Maladie de Crohn (granulome épithélioïde sans nécrose caséeuse, fissures, atteinte transmurale, cryptite/microabcès cryptiques) et piège de la dysplasie sur colite."},
    {"slug": "poss_anapath_sarcome_os", "module_id": "anapath", "sub_discipline": "Anatomopathologie", "course_hints": ["sarcomes", "tumeurs osseuses"], "focus": "Masse profonde des parties molles ou tumeur osseuse métaphysaire agressive : biopsie chirurgicale/trocart sur le trajet d'exérèse futur, IHC MDM2/CDK4, piège fatal de l'énucléation sans RCP."},

    # --- ENDOCRINO-DERMATO (7 complex dossiers from real uploaded docs) ---
    {"slug": "poss_endo_thyrotox_amiodarone", "module_id": "endocrino-dermato", "sub_discipline": "Endocrinologie", "course_hints": ["hyperthyroïdies"], "focus": "Crise aiguë thyrotoxique / cardiothyréose ou hyperthyroïdie induite par l'amiodarone (Type I vs Type II) : Doppler thyroïdien, scintigraphie blanche, antithyroïdiens vs corticoïdes vs propranolol."},
    {"slug": "poss_endo_hypocalcemie_post_thyr", "module_id": "endocrino-dermato", "sub_discipline": "Endocrinologie", "course_hints": ["hypocalcémie"], "focus": "Tétanie aiguë hypocalcémique post-thyroïdectomie totale avec allongement du QT, signe de Trousseau et hypomagnésémie : calcul calcémie corrigée, gluconate de calcium IV vs alfacalcidol."},
    {"slug": "poss_endo_pheo_paroxysme", "module_id": "endocrino-dermato", "sub_discipline": "Endocrinologie", "course_hints": ["phéochromocytome"], "focus": "Incidentalome surrénalien / poussées hypertensives avec triade de Ménard : piège mortel des bêtabloquants avant alpha-bloquants, dérivés méthoxylés urinaires/plasmatiques, recherche NEM2."},
    {"slug": "poss_endo_hypoglycemie_insulinome", "module_id": "endocrino-dermato", "sub_discipline": "Endocrinologie", "course_hints": ["hypoglycémies"], "focus": "Hypoglycémie organique chez patient non diabétique (triade de Whipple, épreuve de jeûne) : distinguer insulinome, prise factice de sulfamides ou d'insuline exogène via peptide C, pro-insuline et dosage toxicologique."},
    {"slug": "poss_dermato_toxidermie_dress", "module_id": "endocrino-dermato", "sub_discipline": "Dermatologie", "course_hints": ["toxidermies"], "focus": "Toxidermie sévère fébrile sous allopurinol / carbamazépine : différencier DRESS (éosinophilie, cytolyse hépatique, ganglions, S2-S8) de la nécrolyse épidermique toxique Lyell (Nikolsky, muqueuses), imputabilité et éviction définitive."},
    {"slug": "poss_dermato_psoriasis_biotherapie", "module_id": "endocrino-dermato", "sub_discipline": "Dermatologie", "course_hints": ["psoriasis"], "focus": "Psoriasis érythrodermique et rhumatisme psoriasique grave déclenché par corticothérapie générale inappropriée (rebond !) : bilan pré-méthotrexate / pré-anti-TNF (Quantiféron, VHB/VHC/VIH) et pièges."},
    {"slug": "poss_dermato_lepre_reaction", "module_id": "endocrino-dermato", "sub_discipline": "Dermatologie", "course_hints": ["lèpre", "érythème noueux"], "focus": "Névrite cubitale hypertrophique avec macules hypochromiques anesthésiques (lèpre TT vs LL) et réaction de réversion / érythème noueux lépreux (réaction type II) sous polychimiothérapie."},

    # --- HEMATO-ONCO (6 complex dossiers from real uploaded docs) ---
    {"slug": "poss_hemato_myelome_rein", "module_id": "hemato-onco", "sub_discipline": "Hématologie", "course_hints": ["myélome"], "focus": "Myélome multiple symptomatique avec insuffisance rénale aiguë (tubulopathie myélomateuse), hypercalcémie et lacunes osseuses : piège des produits de contraste iodés / AINS, critères CRAB/SLiM, R-ISS."},
    {"slug": "poss_hemato_vaquez_thrombose", "module_id": "hemato-onco", "sub_discipline": "Hématologie", "course_hints": ["polyglobulies"], "focus": "Polyglobulie de Vaquez (érythromélalgie, prurit aquagénique, thrombose splanchnique/Budd-Chiari) : JAK2 V617F, EPO sérique basse, diagnostic différentiel avec polyglobulies secondaires, saignées + aspirine + hydroxyurée."},
    {"slug": "poss_hemato_lyse_tumorale", "module_id": "hemato-onco", "sub_discipline": "Hématologie", "course_hints": ["urgences oncologiques", "lymphomes"], "focus": "Syndrome de lyse tumorale aiguë sur lymphome agressif de haut grade (hyperkaliémie, hyperphosphatémie, hypocalcémie, hyperuricémie) : Cairo-Bishop, rasburicase vs allopurinol, contre-indication d'alcalinisation."},
    {"slug": "poss_hemato_llc_autoimmune", "module_id": "hemato-onco", "sub_discipline": "Hématologie", "course_hints": ["lymphoide chronique", "anémie hémolytique"], "focus": "Leucémie lymphoïde chronique avec anémie hémolytique auto-immune à Coombs chaud positif et syndrome d'Evans : score de Matutes, ombres de Gumprecht, classification de Binet et del(17p)/TP53."},
    {"slug": "poss_hemato_purpura_thrombopenie", "module_id": "hemato-onco", "sub_discipline": "Hématologie", "course_hints": ["hémorragique"], "focus": "Syndrome hémorragique sévère aigu sur thrombopénie profonde vs microangiopathie thrombotique (schizocytes + LDH + fièvre) : piège fatal de la transfusion plaquettaire dans un PTT vs PTI aigu."},
    {"slug": "poss_hemato_lmc_transformation", "module_id": "hemato-onco", "sub_discipline": "Hématologie", "course_hints": ["myéloide chronique"], "focus": "Leucémie myéloïde chronique hyperleucocytaire avec splénomégalie géante et priapisme / leucostase : chromosome Philadelphie t(9;22) / BCR-ABL1, myélémie harmonieuse sans hiatus, phases chronique/accélérée/blastique et ITK."},

    # --- NEURO-NEUROCHIR (6 complex dossiers from real uploaded docs) ---
    {"slug": "poss_neuro_hsa_vasospasme", "module_id": "neuro-neurochir", "sub_discipline": "Neurochirurgie", "course_hints": ["hsa spontanée"], "focus": "Céphalée en coup de tonnerre avec TDM cérébrale normale à H30 -> PL obligatoire (xanthochromie / 3 tubes), scores WFNS & Fisher, nimodipine préventive du vasospasme et sécurisation précoce de l'anévrisme."},
    {"slug": "poss_neuro_tvc_grossesse", "module_id": "neuro-neurochir", "sub_discipline": "Neurologie", "course_hints": ["thrombophlébite cérébrale"], "focus": "Thrombophlébite cérébrale en post-partum / sous œstroprogestatifs avec crises focales et infarctus hémorragique : IRM/ARM veineuse (signe du delta vide), anticoagulation curative MALGRÉ le saignement parenchymateux."},
    {"slug": "poss_neuro_gbs_detresse", "module_id": "neuro-neurochir", "sub_discipline": "Neurologie", "course_hints": ["neuropathie périphérique"], "focus": "Tétraparésie ascendante aréflexique post-infectieuse avec diplégie faciale et atteinte respiratoire : dissociation albumino-cytologique retardée au LCR, ENMG démyélinisant, IgIV vs échanges plasmatiques et inefficacité des corticoïdes."},
    {"slug": "poss_neuro_comp_med_metastase", "module_id": "neuro-neurochir", "sub_discipline": "Neurochirurgie", "course_hints": ["compressions médullaires"], "focus": "Compression médullaire lente (triade syndrome rachidien + lésionnel + sous-lésionnel, niveau T6) : IRM médullaire T1/T2 injectée en urgence absolue, corticothérapie IV haute dose et décompression avant paraplégie flasque."},
    {"slug": "poss_neuro_suppurations_abces", "module_id": "neuro-neurochir", "sub_discipline": "Neurochirurgie", "course_hints": ["suppurations"], "focus": "Abcès cérébral / empyème sous-dural post-sinusien (triade de Bergman fièvre + HTIC + déficit focal) : contre-indication de la PL avant imagerie, image en cocarde à l'IRM de diffusion, ponction stéréotaxique + tri-antibiothérapie."},
    {"slug": "poss_neuro_adenome_apoplexie", "module_id": "neuro-neurochir", "sub_discipline": "Neurochirurgie", "course_hints": ["adénomes hypophysaires"], "focus": "Apoplexie hypophysaire aiguë (céphalée en coup de tonnerre, diplopie par atteinte III/VI, hémianopsie bitemporale, hyponatrémie) : hydrocortisone IV urgente avant tout bilan, décompression transsphénoïdale vs surveillance."},
]


def _call_gemini(
    parts: list[dict[str, Any]],
    models: list[str],
    temperature: float = 0.2,
    timeout: int = 120,
    rotate_idx: int = 0,
) -> dict[str, Any]:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY manquante.")

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": temperature,
            "responseMimeType": "application/json",
        },
    }
    ordered = models[rotate_idx % len(models) :] + models[: rotate_idx % len(models)]
    last_err: Exception | None = None
    for attempt in range(4):
        now = time.time()
        with _MODEL_LOCK:
            candidates = [m for m in ordered if m not in _DEAD_MODELS and _COOLDOWN_UNTIL.get(m, 0.0) <= now]
            if not candidates:
                candidates = [m for m in ordered if m not in _DEAD_MODELS]
        for model in candidates:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    txt = body["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = json.loads(txt)
                    if isinstance(parsed, list) and parsed:
                        return {"questions": parsed} if isinstance(parsed[0], dict) and "stem" in parsed[0] else parsed[0]
                    return parsed
            except urllib.error.HTTPError as he:
                err_txt = he.read().decode("utf-8", errors="ignore")[:300]
                last_err = RuntimeError(f"HTTP {he.code} on {model}: {err_txt}")
                with _MODEL_LOCK:
                    if he.code == 404 or ("free_tier" in err_txt and "limit: 0" in err_txt):
                        _DEAD_MODELS.add(model)
                    elif he.code == 429:
                        if "limit: 20" in err_txt or "PerDay" in err_txt:
                            _DEAD_MODELS.add(model)
                        else:
                            _COOLDOWN_UNTIL[model] = time.time() + 25.0
                    elif he.code in (500, 502, 503, 504):
                        _COOLDOWN_UNTIL[model] = time.time() + 12.0
                continue
            except Exception as exc:
                last_err = exc
                continue
        time.sleep(6.0 * (attempt + 1))
    raise RuntimeError(f"Gemini call failed: {last_err}")


def _sample_pdf_jpegs(pdf_path: Path, max_pages: int = 10) -> list[bytes]:
    """Render evenly sampled pages of a scanned PDF as compact JPEG bytes."""
    import pypdf

    try:
        n_pages = len(pypdf.PdfReader(str(pdf_path)).pages)
    except Exception:
        n_pages = 10
    n_pages = max(1, n_pages)
    if n_pages <= max_pages:
        chosen = list(range(1, n_pages + 1))
    else:
        step = (n_pages - 1) / (max_pages - 1)
        chosen = sorted({max(1, min(n_pages, round(1 + i * step))) for i in range(max_pages)})

    imgs: list[bytes] = []
    with tempfile.TemporaryDirectory() as tmpd:
        for pno in chosen:
            prefix = Path(tmpd) / f"pg_{pno:03d}"
            try:
                subprocess.run(
                    ["pdftoppm", "-jpeg", "-jpegopt", "quality=70", "-r", "85", "-f", str(pno), "-l", str(pno), "-singlefile", str(pdf_path), str(prefix)],
                    check=True,
                    capture_output=True,
                    timeout=20,
                )
                jpg = Path(f"{prefix}.jpg")
                if jpg.exists() and jpg.stat().st_size > 0:
                    imgs.append(jpg.read_bytes())
            except Exception:
                continue
    return imgs


def _gather_course_context(conn, course_row) -> dict[str, Any]:
    """Assemble full text and/or sampled scanned page JPEGs for a course."""
    cid = course_row["id"]
    files = conn.execute(
        """
        SELECT id, name, category, local_path, text_chars, page_count, version_tag
        FROM drive_files
        WHERE course_id = ? AND category IN ('cours', 'resume_mohamed') AND local_path IS NOT NULL
        ORDER BY CASE WHEN category='cours' THEN 0 ELSE 1 END,
                 CASE WHEN version_tag='2026-2027' THEN 0 WHEN version_tag='final' THEN 1 ELSE 2 END,
                 text_chars DESC
        """,
        (cid,),
    ).fetchall()

    text_blocks: list[str] = []
    image_parts: list[dict[str, Any]] = []
    doc_names: list[str] = []
    scanned_pdfs: list[Path] = []

    for f in files:
        lp = DATA_DIR / f["local_path"]
        if not lp.exists():
            continue
        doc_names.append(f["name"])
        tchars, _, txt = extract_full_text(lp, max_chars=24000)
        if tchars >= 350 and txt:
            if sum(len(b) for b in text_blocks) < 28000:
                text_blocks.append(f"=== DOCUMENT [{f['category']}] : {f['name']} ===\n{txt[:20000]}")
        elif f["name"].lower().endswith(".pdf"):
            scanned_pdfs.append(lp)

    # Render scanned pages only if total text across all files is thin (< 1500 chars)
    if sum(len(b) for b in text_blocks) < 1500 and scanned_pdfs:
        per_pdf = max(4, 10 // len(scanned_pdfs))
        for spdf in scanned_pdfs[:2]:
            for jb in _sample_pdf_jpegs(spdf, max_pages=per_pdf):
                image_parts.append({
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": base64.b64encode(jb).decode("ascii"),
                    }
                })

    existing_qs = [
        r["stem"]
        for r in conn.execute(
            "SELECT stem FROM questions WHERE course_id = ? AND COALESCE(is_predicted, 0) = 0 LIMIT 10",
            (cid,),
        ).fetchall()
    ]
    return {
        "doc_names": doc_names,
        "combined_text": "\n\n".join(text_blocks)[:28000],
        "image_parts": image_parts[:10],
        "existing_stems": existing_qs,
        "has_real_docs": bool(text_blocks or image_parts),
    }


def _question_prompt(c_row, ctx: dict[str, Any], target_count: int) -> str:
    mod_id = c_row["module_id"]
    if mod_id == "anapath":
        fmt_rule = (
            "Pour Anatomopathologie (APS) : génère au moins 2 questions au format 'qcm_group' "
            "(5 propositions minuscules 'a'..'e' dans `statements` suivies de 5 combinaisons 'A'..'E' dans `options` comme 'a;c;d', et UNE SEULE lettre majuscule dans `correct_answers`), "
            "et le reste en 'qcm_multi' (5 options A..E, 2 à 4 réponses justes). Piège sur marqueurs IHC, histologie exacte, classifications OMS/TNM et contre-indications de biopsie/extemporanée."
        )
    elif mod_id == "neuro-neurochir":
        fmt_rule = (
            "Pour Neurologie / Neurochirurgie : génère 2 questions rédactionnelles 'qroc' (courtes mais exigeantes : conduite en urgence, triade, contre-indication, échelle ou bilan, avec `rubric_points` contenant 4 puces courtes très précises, `options: []`, `correct_answers: []`), "
            "et le reste en 'qcm_multi' cliniques pointus."
        )
    else:
        fmt_rule = (
            "Génère des 'qcm_multi' à 5 propositions A..E (2 à 4 réponses vraies — JAMAIS de question triviale à 1 seul mot). "
            "Cible les seuils numériques exacts, les exceptions, les diagnostics différentiels piégeux, les bilans hiérarchisés et les contre-indications thérapeutiques."
        )

    existing_block = "\n".join(f"- {s}" for s in ctx["existing_stems"][:8]) or "Aucune annale indexée (chapitre à fort risque de question inédite !)"
    docs_list = ", ".join(ctx["doc_names"]) if ctx["doc_names"] else "Programme officiel S7 & corpus du professeur"

    return f"""Tu es membre du jury d'examen de 4e année de Médecine (Semestre 7, FMPO Oujda).
Analyse en profondeur les supports ci-dessous pour le cours :
- Module : {c_row['module_id']} ({c_row['sub_discipline']})
- Cours : {c_row['canonical_title']}
- Professeur : {c_row['professor']}
- Statut : promo={c_row['promo_status']} / fréquence={c_row['exam_frequency']}
- Documents disponibles : {docs_list}

Questions déjà présentes dans les annales/QE (NE PAS LES RECOPIER — crée des questions inédites et plus dures sur les points non encore testés ou actualisés) :
{existing_block}

MISSION :
Produis EXACTEMENT {target_count} questions d'examen DIFFICILES (« wa3rin » / discriminantes / pièges classiques de jury FMPO) tirées des notions précises des documents fournis (ou des images de slides jointes).
{fmt_rule}

Règles strictes :
1. Aucune question triviale de définition basique. Chaque item doit exiger une réflexion clinique, un seuil chiffré exact, une exception, un marqueur ou une conduite hiérarchisée.
2. Pour `qcm_group` : `statements` a exactement 5 objets `a..e`, `options` a exactement 5 objets `A..E` listant des lettres (ex `"a ; c ; e"`), et `correct_answers` a exactement `["X"]`.
3. Pour `qcm_multi` : `statements: []`, `options` a exactement 5 objets `A..E`, `correct_answers` liste toutes les lettres exactes vraies (ex `["A","C","D"]`).
4. Pour `qroc` : `statements: []`, `options: []`, `correct_answers: []`, et `rubric_points` contient 4 points-clés concis (chacun <= 14 mots avec les mots médicaux clés).
5. `difficulty_tier` : utilise `"piege_jury"` (piège mortel / confusion classique) ou `"wa3ra"` (synthèse clinique / seuil difficile).
6. `likelihood_score` : entier entre 82 et 98 selon l'importance examinable de cette notion dans le cours.
7. `doc_evidence` : cite précisément le document source et la notion (ex: `"{ctx['doc_names'][0] if ctx['doc_names'] else c_row['canonical_title']} — Section critère/traitement..."`).
8. `explanation` : explication rigoureuse en français expliquant POURQUOI les bonnes réponses sont exactes ET pourquoi les distracteurs sont des pièges.

Réponds UNIQUEMENT avec un objet JSON strict au format :
{{
  "questions": [
    {{
      "question_type": "qcm_multi",
      "vignette_text": null,
      "stem": "énoncé exact ou mini-vignette clinique exigeante",
      "statements": [],
      "options": [{{"letter": "A", "text": "..."}}, {{"letter": "B", "text": "..."}}, {{"letter": "C", "text": "..."}}, {{"letter": "D", "text": "..."}}, {{"letter": "E", "text": "..."}}],
      "correct_answers": ["A", "C"],
      "rubric_points": [],
      "difficulty_tier": "piege_jury",
      "likelihood_score": 92,
      "doc_evidence": "...",
      "explanation": "..."
    }}
  ]
}}

TEXTE EXTRAIT DES SUPPORTS DU COURS :
{ctx['combined_text']}
"""


def _normalize_letter_items(items: Any, lowercase: bool = False) -> list[dict[str, str]]:
    """Coerce Gemini statement/option lists cleanly into [{letter, text}] regardless of key variants."""
    if not isinstance(items, list):
        return []
    letters = "abcde" if lowercase else "ABCDE"
    out: list[dict[str, str]] = []
    for i, item in enumerate(items):
        fallback_l = letters[i] if i < len(letters) else str(i + 1)
        if isinstance(item, str):
            raw_s = item.strip()
            m = re.match(r"^([A-Ea-e])[).:\-]\s*(.+)$", raw_s)
            l_val = m.group(1) if m else fallback_l
            t_val = m.group(2).strip() if m else raw_s
        elif isinstance(item, dict):
            l_raw = item.get("letter") or item.get("key") or item.get("id") or item.get("label")
            t_raw = item.get("text") or item.get("statement") or item.get("option") or item.get("content") or item.get("value")
            if l_raw is None and len(item) == 1:
                k, v = next(iter(item.items()))
                l_raw, t_raw = k, v
            l_val = str(l_raw or fallback_l).strip()
            t_val = str(t_raw or "").strip()
        else:
            continue
        if not t_val:
            continue
        l_clean = l_val.lower() if lowercase else l_val.upper()
        l_clean = re.sub(r"[^a-zA-Z0-9]", "", l_clean)[:2] or fallback_l
        out.append({"letter": l_clean, "text": t_val})
    return out


def _validate_question_item(q: dict[str, Any], default_doc: str) -> dict[str, Any] | None:
    if not isinstance(q, dict):
        return None
    qtype = str(q.get("question_type", "qcm_multi")).strip()
    if qtype not in ("qcm_multi", "qcm_group", "qroc"):
        return None
    stem = str(q.get("stem") or "").strip()
    if len(stem) < 18:
        return None

    stmts = _normalize_letter_items(q.get("statements") or [], lowercase=True)
    opts = _normalize_letter_items(q.get("options") or [], lowercase=False)
    corr = [str(x).strip().upper()[:2] for x in (q.get("correct_answers") or []) if str(x).strip()]
    rubric = [str(x).strip() for x in (q.get("rubric_points") or []) if str(x).strip()]

    if qtype == "qcm_group":
        if len(stmts) < 4 or len(opts) < 4 or len(corr) != 1:
            return None
        valid_letters = {o["letter"] for o in opts}
        if corr[0] not in valid_letters:
            return None
    elif qtype == "qcm_multi":
        if len(opts) < 4 or not corr:
            return None
        valid_letters = {o["letter"] for o in opts}
        corr = [x for x in corr if x in valid_letters]
        if not corr:
            return None
        stmts = []
    elif qtype == "qroc":
        if len(rubric) < 2:
            return None
        stmts, opts, corr = [], [], []

    tier = str(q.get("difficulty_tier") or "wa3ra").strip().lower()
    if tier not in ("piege_jury", "wa3ra"):
        tier = "wa3ra"
    try:
        score = max(75, min(99, int(q.get("likelihood_score") or 88)))
    except Exception:
        score = 88

    return {
        "question_type": qtype,
        "vignette_text": str(q.get("vignette_text")).strip() if q.get("vignette_text") else None,
        "stem": stem,
        "statements": stmts,
        "options": opts,
        "correct_answers": corr,
        "rubric_points": rubric,
        "difficulty_tier": tier,
        "likelihood_score": score,
        "doc_evidence": str(q.get("doc_evidence") or default_doc).strip()[:400],
        "explanation": str(q.get("explanation") or "").strip(),
    }


def _build_case_prompt(bp: dict[str, Any], matched_courses: list[dict[str, Any]], combined_text: str, doc_names: list[str]) -> str:
    c_summary = ", ".join(f"{c['canonical_title']} ({c['professor']})" for c in matched_courses) or bp["sub_discipline"]
    return f"""Tu es professeur chef de service clinique à la FMPO d'Oujda. Rédige UN cas clinique progressif de TRÈS HAUT NIVEAU (« cas clinique nadi & sélectif ») en 4 étapes cohérentes.

Cible :
- Module : {bp['module_id']} / {bp['sub_discipline']}
- Cours associés : {c_summary}
- Documents analysés : {', '.join(doc_names) or 'Programme S7 FMPO'}
- Axe clinique précis : {bp['focus']}

Exigences cliniques strictes :
1. `patient_summary` : présentation réaliste aux urgences ou en consultation spécialisée (âge, terrain, antécédents, chronologie horaire exacte, prise médicamenteuse éventuelle créant un piège).
2. `vitals_json` : exactement 5 à 6 constantes chiffrées pertinentes (ex: PA, FC, SpO2, T°, Glycémie ou marqueur clé).
3. `steps_json` : EXACTEMENT 4 étapes progressives :
   - Step 1 (`diagnosis`) : Raisonnement diagnostique et piège sémiologique/étiologique. Format `"qcm_multi"`, 5 options A..E (`2` ou `3` exactes).
   - Step 2 (`workup_choice`) : Bilan paraclinique hiérarchisé (avec distracteurs piégeux : examen contre-indiqué, retardateur ou faussement rassurant). Format `"qcm_multi"`, 5 options A..E.
   - Step 3 (`management`) : Conduite thérapeutique immédiate, posologie/voie ou ordre critique avant autre geste. Format `"qcm_multi"`, 5 options A..E.
   - Step 4 (`complication` ou `synthesis`) : Évolution aiguë à H+6/J+4 ou critère pronostique/anatomopathologique décisionnel. Format `"qcm_multi"`, 5 options A..E.
4. Chaque étape doit contenir :
   - `clinical_reveal`: résultat clinique ou biologique chiffré réaliste dévoilé à cette étape (cohérent avec les constantes !).
   - `red_flags`: 1 ou 2 pièges fatals concrets à ne jamais faire.
   - `teaching_pearl`: perle de synthèse rigoureuse façon jury FMPO.
   - `points`: 2.
5. `takeaway_points`: 3 à 4 réflexes d'or finaux à retenir pour l'examen S7.
6. `doc_evidence`: cite les supports de cours exploités (`{', '.join(doc_names[:3]) or c_summary}`).

Réponds UNIQUEMENT en JSON strict :
{{
  "title": "...",
  "difficulty": "Très élevée",
  "source_tag": "PRÉDICTION S7 · ...",
  "patient_summary": "...",
  "vitals_json": {{"PA": "...", "FC": "...", "SpO2": "...", "T°": "..."}},
  "steps_json": [
    {{
      "step_number": 1,
      "step_type": "diagnosis",
      "prompt": "...",
      "clinical_reveal": "...",
      "question_format": "qcm_multi",
      "options": [{{"letter": "A", "text": "..."}}, {{"letter": "B", "text": "..."}}, {{"letter": "C", "text": "..."}}, {{"letter": "D", "text": "..."}}, {{"letter": "E", "text": "..."}}],
      "correct_answers": ["A", "D"],
      "red_flags": ["..."],
      "teaching_pearl": "...",
      "points": 2
    }}
  ],
  "takeaway_points": ["...", "...", "..."],
  "doc_evidence": "..."
}}

EXTRAITS DES DOCUMENTS DE COURS ANALYSÉS :
{combined_text[:26000]}
"""


def _validate_case(raw: dict[str, Any], bp: dict[str, Any], course_id: int | None) -> dict[str, Any] | None:
    title = str(raw.get("title") or "").strip()
    summary = str(raw.get("patient_summary") or "").strip()
    steps = raw.get("steps_json") or []
    if len(title) < 10 or len(summary) < 25 or len(steps) < 3:
        return None
    clean_steps = []
    for idx, st in enumerate(steps[:4], 1):
        if not isinstance(st, dict):
            return None
        opts = _normalize_letter_items(st.get("options") or [], lowercase=False)
        valid = {o["letter"] for o in opts}
        corr = [str(x).strip().upper()[:2] for x in (st.get("correct_answers") or []) if str(x).strip().upper()[:2] in valid]
        if len(opts) < 4 or not corr:
            return None
        clean_steps.append({
            "step_number": idx,
            "step_type": str(st.get("step_type") or "diagnosis"),
            "prompt": str(st.get("prompt") or "").strip(),
            "clinical_reveal": str(st.get("clinical_reveal") or "").strip(),
            "question_format": "qcm_multi",
            "options": opts,
            "correct_answers": corr,
            "red_flags": [str(r).strip() for r in (st.get("red_flags") or []) if str(r).strip()],
            "teaching_pearl": str(st.get("teaching_pearl") or "").strip(),
            "points": int(st.get("points") or 2),
        })
    return {
        "slug": bp["slug"],
        "module_id": bp["module_id"],
        "sub_discipline": bp["sub_discipline"],
        "course_id": course_id,
        "title": title,
        "difficulty": str(raw.get("difficulty") or "Très élevée"),
        "source_tag": str(raw.get("source_tag") or f"PRÉDICTION S7 · {bp['sub_discipline']}"),
        "patient_summary": summary,
        "vitals_json": raw.get("vitals_json") or {},
        "steps_json": clean_steps,
        "takeaway_points": [str(t).strip() for t in (raw.get("takeaway_points") or []) if str(t).strip()],
        "doc_evidence": str(raw.get("doc_evidence") or bp["focus"]).strip()[:400],
    }


def main() -> None:
    init_db(DB_PATH)
    conn = get_conn()
    cache: dict[str, Any] = json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {"courses": {}, "cases": {}}
    cache.setdefault("courses", {})
    cache.setdefault("cases", {})

    # 1. Select all real courses with documents (or priority MAJ 2026-2027 / 0-annales chapters)
    courses = conn.execute(
        """
        SELECT co.*,
          (SELECT COUNT(*) FROM questions q WHERE q.course_id = co.id AND COALESCE(q.is_predicted, 0) = 0) as annale_cnt
        FROM courses co
        WHERE co.canonical_title NOT IN ('Total :', 'Restant :')
        ORDER BY co.module_id, co.row_order
        """
    ).fetchall()

    contexts_by_cid: dict[int, dict[str, Any]] = {}
    course_jobs: list[tuple[dict[str, Any], dict[str, Any], int]] = []
    for c in courses:
        cid_str = str(c["id"])
        ctx = _gather_course_context(conn, c)
        contexts_by_cid[c["id"]] = ctx
        if not ctx["has_real_docs"]:
            continue
        # 4 tough questions for 0-annale or high-yield courses, 3 for others with docs
        n_target = 4 if (c["annale_cnt"] == 0 or c["exam_frequency"] == "high_yield" or c["promo_status"] == "V") else 3
        if cid_str not in cache["courses"] or len(cache["courses"][cid_str].get("questions", [])) == 0:
            course_jobs.append((dict(c), ctx, n_target))

    print(f"Found {len(courses)} courses; {len(course_jobs)} doc-backed courses remaining to generate questions...")

    def _run_course_job(job: tuple[int, dict[str, Any], dict[str, Any], int]) -> tuple[str, dict[str, Any]]:
        j_idx, c_row, ctx, n_target = job
        prompt = _question_prompt(c_row, ctx, n_target)
        parts: list[dict[str, Any]] = [{"text": prompt}] + ctx["image_parts"]
        res = _call_gemini(parts, MODELS_QUESTIONS, temperature=0.25, timeout=120, rotate_idx=j_idx)
        default_doc = ", ".join(ctx["doc_names"]) if ctx["doc_names"] else c_row["canonical_title"]
        cleaned = []
        for q in (res.get("questions") or []):
            vq = _validate_question_item(q, default_doc)
            if vq:
                cleaned.append(vq)
        return str(c_row["id"]), {
            "course_title": c_row["canonical_title"],
            "module_id": c_row["module_id"],
            "sub_discipline": c_row["sub_discipline"],
            "professor": c_row["professor"],
            "annale_cnt": c_row["annale_cnt"],
            "doc_names": ctx["doc_names"],
            "questions": cleaned,
        }

    if course_jobs:
        numbered_jobs = [(i, c_row, ctx, n_target) for i, (c_row, ctx, n_target) in enumerate(course_jobs)]
        with ThreadPoolExecutor(max_workers=3) as pool:
            futs = [pool.submit(_run_course_job, j) for j in numbered_jobs]
            for idx, fut in enumerate(as_completed(futs), 1):
                try:
                    cid_str, entry = fut.result()
                    with _MODEL_LOCK:
                        cache["courses"][cid_str] = entry
                        CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
                    print(f"  [{idx}/{len(course_jobs)}] OK {entry['module_id']} · {entry['course_title']} -> {len(entry['questions'])} Q ({', '.join(entry['doc_names'][:2])})")
                except Exception as exc:
                    print(f"  [{idx}/{len(course_jobs)}] ERR: {exc}")

    # 2. Generate showcase Complex Clinical Cases from real docs
    pending_bps = [bp for bp in COMPLEX_CASE_BLUEPRINTS if bp["slug"] not in cache["cases"]]
    print(f"Generating {len(pending_bps)} complex multi-step clinical cases...")

    case_jobs: list[tuple[dict[str, Any], list[dict[str, Any]], str, list[str], list[dict[str, Any]]]] = []
    for bp in pending_bps:
        matched = []
        text_parts: list[str] = []
        doc_names: list[str] = []
        image_parts: list[dict[str, Any]] = []
        for c in courses:
            if c["module_id"] != bp["module_id"]:
                continue
            title_low = c["canonical_title"].lower()
            if any(h in title_low for h in bp["course_hints"]):
                matched.append(dict(c))
                ctx = contexts_by_cid[c["id"]]
                if ctx["combined_text"]:
                    text_parts.append(ctx["combined_text"][:14000])
                doc_names.extend(ctx["doc_names"])
                image_parts.extend(ctx["image_parts"][:4])
        case_jobs.append((bp, matched, "\n\n".join(text_parts), list(dict.fromkeys(doc_names)), image_parts[:8]))

    def _run_case_job(cjob: tuple[int, dict[str, Any], list[dict[str, Any]], str, list[str], list[dict[str, Any]]]) -> tuple[str, dict[str, Any] | None]:
        c_idx, bp, matched, combined_text, doc_names, image_parts = cjob
        prompt = _build_case_prompt(bp, matched, combined_text, doc_names)
        parts: list[dict[str, Any]] = [{"text": prompt}] + image_parts
        raw = _call_gemini(parts, MODELS_CASES, temperature=0.25, timeout=140, rotate_idx=c_idx)
        primary_cid = matched[0]["id"] if matched else None
        validated = _validate_case(raw, bp, primary_cid)
        return bp["slug"], validated

    if case_jobs:
        numbered_cjobs = [(i, *cj) for i, cj in enumerate(case_jobs)]
        with ThreadPoolExecutor(max_workers=3) as pool:
            futs = [pool.submit(_run_case_job, cj) for cj in numbered_cjobs]
            for idx, fut in enumerate(as_completed(futs), 1):
                try:
                    slug, case_obj = fut.result()
                    if case_obj:
                        with _MODEL_LOCK:
                            cache["cases"][slug] = case_obj
                            CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
                        print(f"  [Case {idx}/{len(pending_bps)}] OK {slug}: {case_obj['title'][:65]}")
                    else:
                        print(f"  [Case {idx}/{len(pending_bps)}] INVALID {slug}")
                except Exception as exc:
                    print(f"  [Case {idx}/{len(pending_bps)}] ERR: {exc}")

    # 3. Persist cleanly into SQLite (`is_predicted = 1`) without disturbing annales
    conn.execute("DELETE FROM questions WHERE is_predicted = 1")
    conn.execute("DELETE FROM clinical_cases WHERE is_predicted = 1")

    q_inserted = 0
    for cid_str, entry in sorted(cache["courses"].items(), key=lambda x: int(x[0])):
        cid = int(cid_str)
        ann_cnt = int(entry.get("annale_cnt") or 0)
        src_lbl = f"PRÉDICTION COURS · {entry['professor']}" if ann_cnt > 0 else f"PRÉDICTION HORS-ANNALES · {entry['professor']}"
        for idx, q in enumerate(entry.get("questions") or [], 1):
            ext_key = f"pred_c{cid}_{idx}"
            conn.execute(
                """
                INSERT INTO questions (
                    external_key, module_id, sub_discipline, course_id, professor,
                    source_file_id, source_label, exam_year, session, question_number,
                    vignette_group_id, vignette_text, question_type, stem,
                    statements_json, options_json, correct_answers_json, rubric_json,
                    explanation, verification_status, scan_page_image,
                    recurrence_count, frequency_tag, is_predicted, difficulty_tier,
                    likelihood_score, doc_evidence
                ) VALUES (?, ?, ?, ?, ?, NULL, ?, '2026-2027', 'Possible', ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, 'ai_predicted', NULL, 1, 'predicted', 1, ?, ?, ?)
                """,
                (
                    ext_key,
                    entry["module_id"],
                    entry["sub_discipline"],
                    cid,
                    entry["professor"],
                    src_lbl,
                    idx,
                    q.get("vignette_text"),
                    q["question_type"],
                    q["stem"],
                    json.dumps(q["statements"], ensure_ascii=False),
                    json.dumps(q["options"], ensure_ascii=False),
                    json.dumps(q["correct_answers"], ensure_ascii=False),
                    json.dumps({"points": q["rubric_points"]}, ensure_ascii=False),
                    q["explanation"],
                    q["difficulty_tier"],
                    q["likelihood_score"],
                    q["doc_evidence"],
                ),
            )
            q_inserted += 1

    c_inserted = 0
    for slug, case_obj in cache["cases"].items():
        if not case_obj:
            continue
        conn.execute(
            """
            INSERT INTO clinical_cases (
                slug, module_id, sub_discipline, course_id, title, difficulty,
                source_tag, patient_summary, vitals_json, steps_json, takeaway_points,
                is_predicted, doc_evidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (
                case_obj["slug"],
                case_obj["module_id"],
                case_obj["sub_discipline"],
                case_obj.get("course_id"),
                case_obj["title"],
                case_obj["difficulty"],
                case_obj["source_tag"],
                case_obj["patient_summary"],
                json.dumps(case_obj["vitals_json"], ensure_ascii=False),
                json.dumps(case_obj["steps_json"], ensure_ascii=False),
                json.dumps(case_obj["takeaway_points"], ensure_ascii=False),
                case_obj["doc_evidence"],
            ),
        )
        c_inserted += 1

    conn.commit()
    print(f"\nCOMPLETE: Inserted {q_inserted} hard Possible Questions + {c_inserted} Complex Clinical Cases from real course documents.")
    conn.close()


if __name__ == "__main__":
    main()
