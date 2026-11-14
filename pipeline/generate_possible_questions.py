#!/usr/bin/env python3
"""Analyze all 113 S7 courses (lecture PDFs, PPTX, DOCX, scanned PDFs via Vision,
and Professor QE / Examen Blanc corpora) to generate strictly validated,
medical-faculty-grade Possible Questions ('piege_jury' / 'wa3ra') and 30 Complex Clinical Cases.
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
from pipeline.ingest_inventory import norm  # noqa: E402
from pipeline.sync_missing_courses import extract_full_text  # noqa: E402

CACHE_PATH = DATA_DIR / "possible_questions_cache.json"
MODELS_QUESTIONS = [
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.1-flash-lite-preview",
    "gemini-flash-lite-latest",
    "gemini-3.6-flash",
    "gemini-4-hydrogen",
]
MODELS_CASES = [
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.1-flash-lite-preview",
    "gemini-flash-lite-latest",
    "gemini-4-hydrogen",
    "gemini-3.6-flash",
]
_MODEL_LOCK = threading.Lock()
_DEAD_MODELS: set[str] = set()
_COOLDOWN_UNTIL: dict[str, float] = {}

# Shared / Professor corpora mapping so 100% of all 113 real courses have rich document context
SHARED_COURSE_DOC_MAP: list[tuple[str, list[str]]] = [
    ("cancer du poumon", ["4 Le cancer broncho-pulmonaire.pdf", "QE PR BENNANI .pdf"]),
    ("pathologie mammaire", ["QE PR KARICH .pdf"]),
    ("tumeurs de la vessie", ["QE PR KARICH .pdf"]),
    ("cancer de l endometre", ["QE PR KARICH .pdf"]),
    ("cancer de la prostate", ["QE PR KARICH .pdf"]),
    ("cancer du col uterin", ["QE PR KARICH .pdf"]),
    ("cancer de l ovaire", ["QE PR KARICH .pdf"]),
    ("adenome hypophysaire", ["Adenomes_hypophysaires_4e_annee_COURS_COMPLET-2.pptx", "Les adénomes hypophysaires presentatin finale (2).pptx", "QE PR LATRECH .pdf"]),
    ("diabete", ["QE PR LATRECH .pdf"]),
    ("denutrition", ["7 Fondamentaux en nutrition.pdf", "QE PR ROUF .pdf"]),
    ("carences vitaminiques", ["7 Fondamentaux en nutrition.pdf", "QE PR ROUF .pdf"]),
    ("troubles de comportements alimentaires", ["7 Fondamentaux en nutrition.pdf", "QE PR ROUF .pdf"]),
    ("hyperaldosteronisme primaire", ["Pheo HAP   pdf.pdf", "QE PR BOUICHRAT .pdf"]),
    ("pediculose et phtiriase", ["Ectoparasitoses 2026-2027 copie.pdf", "R. ectoparasitose.pdf"]),
    ("melanome carcinome", ["QUIZ Amphi.pdf", "QE - ECN ( PARTIE 1 ) .pdf", "QE - ECN ( PARTIE 2 ) .pdf"]),
    ("epidermoide carcinome", ["QUIZ Amphi.pdf", "QE - ECN ( PARTIE 1 ) .pdf", "QE - ECN ( PARTIE 2 ) .pdf"]),
    ("pemphigoide bulleuse", ["Pemphigus 2026. 2027 copie.pdf", "QUIZ Amphi.pdf", "QE - ECN ( PARTIE 1 ) .pdf"]),
    ("dermatite herppetiforme", ["Pemphigus 2026. 2027 copie.pdf", "QUIZ Amphi.pdf", "QE - ECN ( PARTIE 1 ) .pdf"]),
    ("dermatite seborrheique", ["Psoriasis FMPOpdf+.pdf", "QUIZ Amphi.pdf", "QE - ECN ( PARTIE 1 ) .pdf"]),
    ("eczema de contact", ["QUIZ Amphi.pdf", "QE - ECN ( PARTIE 1 ) .pdf", "QE - ECN ( PARTIE 2 ) .pdf"]),
    ("dermatite atopique", ["QUIZ Amphi.pdf", "QE - ECN ( PARTIE 1 ) .pdf", "QE - ECN ( PARTIE 2 ) .pdf"]),
    ("infections cutanees bacteriennes communes", ["Infections folliculaires et non folliculaires pour PDF M copie.pdf", "Partie I infection folliculaire.pdf", "DHDNN pour PDF.pdf"]),
    ("lymphome de hodgkin", ["3 LH .pdf", "2 LNH (1).pdf", "QE PR ALAOUI .pdf"]),
    ("anemie macrocytaire carentielle", ["QE PR HAMAZ .pdf", "1 Anémies ferriprives .pdf"]),
    ("cat devant un purpura", ["1 Le syndrome hémorragique .pdf", "R sd hemorragie.pdf", "QE PR SERRAJ .pdf"]),
    ("cat devant une thrombopenie", ["1 Le syndrome hémorragique .pdf", "R sd hemorragie.pdf", "QE PR SERRAJ .pdf"]),
    ("techniques et principes d exerese", ["Cancérologie Générale.pptx", "QE PR SERJI .pdf", "QE ONCO"]),
    ("les epilepsies", ["CORRECTION EXAMEN BLANC NEUROLOGIE 2025 .pdf", "EXAMEN BLANC NEURO 2025 .pdf"]),
    ("nevralgie", ["CORRECTION EXAMEN BLANC NEUROLOGIE 2025 .pdf", "Les neuropathies périphériques.pdf"]),
    ("myasthenie", ["CORRECTION EXAMEN BLANC NEUROLOGIE 2025 .pdf", "Les myopathies (2).pdf"]),
    ("migraine et cephalees", ["CORRECTION EXAMEN BLANC NEUROLOGIE 2025 .pdf", "THROMBOPHLEBITE CÉRÉBRALE Modified 2026.pdf"]),
    ("sclerose laterale amyotrophique", ["CORRECTION EXAMEN BLANC NEUROLOGIE 2025 .pdf", "Les neuropathies périphériques.pdf"]),
    ("nmosd et mogad", ["3 SEP_.pdf", "CORRECTION EXAMEN BLANC NEUROLOGIE 2025 .pdf"]),
    ("hypertension intracranienne", ["les hydrocéphalies 2024.pdf", "CORRECTION EXAMEN BLANC NEUROLOGIE 2025 .pdf"]),
    ("tumeurs intracraniennes", ["les hydrocéphalies 2024.pdf", "Les adénomes hypophysaires presentatin finale (2).pptx"]),
]

COMPLEX_CASE_BLUEPRINTS: list[dict[str, Any]] = [
    # --- ANAPATH (7 complex dossiers) ---
    {"slug": "poss_anapath_gastrite_malt", "module_id": "anapath", "sub_discipline": "Anatomopathologie", "course_hints": ["gastrites", "lymphomes"], "focus": "Gastrite chronique à HP évoluant vers lymphome gastrique du MALT vs atrophie/métaplasie intestinale, biopsies Sydney/OLGA, IHC CD20/BCL2/t(11;18) et réponse à l'éradication."},
    {"slug": "poss_anapath_estomac_linitis", "module_id": "anapath", "sub_discipline": "Anatomopathologie", "course_hints": ["estomac"], "focus": "Adénocarcinome gastrique à cellules indépendantes en bague à chaton (linite) vs type intestinal de Lauren, curage ganglionnaire, statut HER2 et instabilité microsatellitaire (MSI)."},
    {"slug": "poss_anapath_poumon_molecular", "module_id": "anapath", "sub_discipline": "Anatomopathologie", "course_hints": ["poumon"], "focus": "Carcinome bronchique à petites cellules vs adénocarcinome vs carcinome épidermoïde (TTF-1, p40/p63, synaptophysine/chromogranine/Ki67), économie tissulaire et testing moléculaire EGFR/ALK/ROS1/PD-L1."},
    {"slug": "poss_anapath_rein_foie", "module_id": "anapath", "sub_discipline": "Anatomopathologie", "course_hints": ["rein"], "focus": "Tumeur rénale solide à cellules claires vs carcinome chromophobe vs oncocytome (grade ISUP/Fuhrman, VHL, Hale/CD117/PAX8/CAIX) et règles de la biopsie rénale / néphrectomie."},
    {"slug": "poss_anapath_mici_dysplasie", "module_id": "anapath", "sub_discipline": "Anatomopathologie", "course_hints": ["mici"], "focus": "Rectocolite hémorragique vs Maladie de Crohn (granulome épithélioïde sans nécrose caséeuse, fissures, atteinte transmurale, cryptite/microabcès cryptiques) et piège de la dysplasie sur colite."},
    {"slug": "poss_anapath_sarcome_os", "module_id": "anapath", "sub_discipline": "Anatomopathologie", "course_hints": ["sarcomes", "tumeurs osseuses"], "focus": "Masse profonde des parties molles ou tumeur osseuse métaphysaire agressive : biopsie chirurgicale/trocart sur le trajet d'exérèse futur, IHC MDM2/CDK4, piège fatal de l'énucléation sans RCP."},
    {"slug": "poss_anapath_sein_her2", "module_id": "anapath", "sub_discipline": "Anatomopathologie", "course_hints": ["mammaire"], "focus": "Carcinome mammaire infiltrant de type non spécifique (NST) vs carcinome lobulaire infiltrant (perte E-cadhérine/CDH1) : grade histopronostique SBR/Elston-Ellis, statut RH/HER2 (IHC 2+ équivoque nécessitant FISH/CISH) et Ki67."},

    # --- ENDOCRINO-DERMATO (9 complex dossiers) ---
    {"slug": "poss_endo_thyrotox_amiodarone", "module_id": "endocrino-dermato", "sub_discipline": "Endocrinologie", "course_hints": ["hyperthyroïdies"], "focus": "Crise aiguë thyrotoxique / cardiothyréose ou hyperthyroïdie induite par l'amiodarone (Type I vs Type II) : Doppler thyroïdien, scintigraphie blanche, antithyroïdiens vs corticoïdes vs propranolol."},
    {"slug": "poss_endo_hypocalcemie_post_thyr", "module_id": "endocrino-dermato", "sub_discipline": "Endocrinologie", "course_hints": ["hypocalcémie"], "focus": "Tétanie aiguë hypocalcémique post-thyroïdectomie totale avec allongement du QT, signe de Trousseau et hypomagnésémie : calcul calcémie corrigée, gluconate de calcium IV vs alfacalcidol."},
    {"slug": "poss_endo_pheo_paroxysme", "module_id": "endocrino-dermato", "sub_discipline": "Endocrinologie", "course_hints": ["phéochromocytome", "hyperaldostéronisme"], "focus": "Incidentalome surrénalien / poussées hypertensives avec triade de Ménard : piège mortel des bêtabloquants avant alpha-bloquants, dérivés méthoxylés urinaires/plasmatiques, recherche NEM2."},
    {"slug": "poss_endo_hypoglycemie_insulinome", "module_id": "endocrino-dermato", "sub_discipline": "Endocrinologie", "course_hints": ["hypoglycémies"], "focus": "Hypoglycémie organique chez patient non diabétique (triade de Whipple, épreuve de jeûne) : distinguer insulinome, prise factice de sulfamides ou d'insuline exogène via peptide C, pro-insuline et dosage toxicologique."},
    {"slug": "poss_endo_diabete_acidocetose", "module_id": "endocrino-dermato", "sub_discipline": "Endocrinologie", "course_hints": ["diabète"], "focus": "Acidocétose diabétique inaugurale sévère vs syndrome d'hyperglycémie hyperosmolaire : piège mortel de l'insulinothérapie IV avant correction d'une kaliémie < 3,3 mmol/L, seuils de réhydratation et prévention de l'œdème cérébral."},
    {"slug": "poss_dermato_toxidermie_dress", "module_id": "endocrino-dermato", "sub_discipline": "Dermatologie", "course_hints": ["toxidermies"], "focus": "Toxidermie sévère fébrile sous allopurinol / carbamazépine : différencier DRESS (éosinophilie, cytolyse hépatique, ganglions, S2-S8) de la nécrolyse épidermique toxique Lyell (Nikolsky, muqueuses), imputabilité et éviction définitive."},
    {"slug": "poss_dermato_psoriasis_biotherapie", "module_id": "endocrino-dermato", "sub_discipline": "Dermatologie", "course_hints": ["psoriasis"], "focus": "Psoriasis érythrodermique et rhumatisme psoriasique grave déclenché par corticothérapie générale inappropriée (rebond !) : bilan pré-méthotrexate / pré-anti-TNF (Quantiféron, VHB/VHC/VIH) et pièges."},
    {"slug": "poss_dermato_lepre_reaction", "module_id": "endocrino-dermato", "sub_discipline": "Dermatologie", "course_hints": ["lèpre", "érythème noueux"], "focus": "Névrite cubitale hypertrophique avec macules hypochromiques anesthésiques (lèpre TT vs LL) et réaction de réversion / érythème noueux lépreux (réaction type II) sous polychimiothérapie."},
    {"slug": "poss_dermato_melanome_pemphigoide", "module_id": "endocrino-dermato", "sub_discipline": "Dermatologie", "course_hints": ["mélanome", "pemphigoide"], "focus": "Tumeur pigmentée ulcérée suspecte de mélanome (règle ABCDE, biopsie-exérèse complète vs biopsie partielle contre-indiquée, indice de Breslow et marges de reprise) chez un sujet âgé présentant par ailleurs des bulles tendues prurigineuses (pemphigoïde bulleuse)."},

    # --- HEMATO-ONCO (7 complex dossiers) ---
    {"slug": "poss_hemato_myelome_rein", "module_id": "hemato-onco", "sub_discipline": "Hématologie", "course_hints": ["myélome"], "focus": "Myélome multiple symptomatique avec insuffisance rénale aiguë (tubulopathie myélomateuse), hypercalcémie et lacunes osseuses : piège des produits de contraste iodés / AINS, critères CRAB/SLiM, R-ISS."},
    {"slug": "poss_hemato_vaquez_thrombose", "module_id": "hemato-onco", "sub_discipline": "Hématologie", "course_hints": ["polyglobulies"], "focus": "Polyglobulie de Vaquez (érythromélalgie, prurit aquagénique, thrombose splanchnique/Budd-Chiari) : JAK2 V617F, EPO sérique basse, diagnostic différentiel avec polyglobulies secondaires, saignées + aspirine + hydroxyurée."},
    {"slug": "poss_hemato_lyse_tumorale", "module_id": "hemato-onco", "sub_discipline": "Hématologie", "course_hints": ["urgences oncologiques", "lymphomes"], "focus": "Syndrome de lyse tumorale aiguë sur lymphome agressif de haut grade (hyperkaliémie, hyperphosphatémie, hypocalcémie, hyperuricémie) : Cairo-Bishop, rasburicase vs allopurinol, contre-indication d'alcalinisation."},
    {"slug": "poss_hemato_llc_autoimmune", "module_id": "hemato-onco", "sub_discipline": "Hématologie", "course_hints": ["lymphoide chronique", "anémie hémolytique"], "focus": "Leucémie lymphoïde chronique avec anémie hémolytique auto-immune à Coombs chaud positif et syndrome d'Evans : score de Matutes, ombres de Gumprecht, classification de Binet et del(17p)/TP53."},
    {"slug": "poss_hemato_purpura_thrombopenie", "module_id": "hemato-onco", "sub_discipline": "Hématologie", "course_hints": ["hémorragique", "purpura", "thrombopénie"], "focus": "Syndrome hémorragique sévère aigu sur thrombopénie profonde vs microangiopathie thrombotique (schizocytes + LDH + fièvre) : piège fatal de la transfusion plaquettaire dans un PTT vs PTI aigu."},
    {"slug": "poss_hemato_lmc_transformation", "module_id": "hemato-onco", "sub_discipline": "Hématologie", "course_hints": ["myéloide chronique"], "focus": "Leucémie myéloïde chronique hyperleucocytaire avec splénomégalie géante et priapisme / leucostase : chromosome Philadelphie t(9;22) / BCR-ABL1, myélémie harmonieuse sans hiatus, phases chronique/accélérée/blastique et ITK."},
    {"slug": "poss_hemato_hodgkin_mediastin", "module_id": "hemato-onco", "sub_discipline": "Hématologie", "course_hints": ["hodgkin"], "focus": "Lymphome de Hodgkin classique médiastinal compressif (masse Bulky, signes B, prurit) : biopsie ganglionnaire excisionalle (cellule de Reed-Sternberg CD30+/CD15+/CD20-/PAX5 faible), bilan d'extension TEP-FDG (score de Deauville) et toxicité pulmonaire de la bléomycine."},

    # --- NEURO-NEUROCHIR (7 complex dossiers) ---
    {"slug": "poss_neuro_hsa_vasospasme", "module_id": "neuro-neurochir", "sub_discipline": "Neurochirurgie", "course_hints": ["hsa spontanée"], "focus": "Céphalée en coup de tonnerre avec TDM cérébrale normale à H30 -> PL obligatoire (xanthochromie / 3 tubes), scores WFNS & Fisher, nimodipine préventive du vasospasme et sécurisation précoce de l'anévrisme."},
    {"slug": "poss_neuro_tvc_grossesse", "module_id": "neuro-neurochir", "sub_discipline": "Neurologie", "course_hints": ["thrombophlébite cérébrale"], "focus": "Thrombophlébite cérébrale en post-partum / sous œstroprogestatifs avec crises focales et infarctus hémorragique : IRM/ARM veineuse (signe du delta vide), anticoagulation curative MALGRÉ le saignement parenchymateux."},
    {"slug": "poss_neuro_gbs_detresse", "module_id": "neuro-neurochir", "sub_discipline": "Neurologie", "course_hints": ["neuropathie périphérique"], "focus": "Tétraparésie ascendante aréflexique post-infectieuse avec diplégie faciale et atteinte respiratoire : dissociation albumino-cytologique retardée au LCR, ENMG démyélinisant, IgIV vs échanges plasmatiques et inefficacité des corticoïdes."},
    {"slug": "poss_neuro_comp_med_metastase", "module_id": "neuro-neurochir", "sub_discipline": "Neurochirurgie", "course_hints": ["compressions médullaires"], "focus": "Compression médullaire lente (triade syndrome rachidien + lésionnel + sous-lésionnel, niveau T6) : IRM médullaire T1/T2 injectée en urgence absolue, corticothérapie IV haute dose et décompression avant paraplégie flasque."},
    {"slug": "poss_neuro_suppurations_abces", "module_id": "neuro-neurochir", "sub_discipline": "Neurochirurgie", "course_hints": ["suppurations"], "focus": "Abcès cérébral / empyème sous-dural post-sinusien (triade de Bergman fièvre + HTIC + déficit focal) : contre-indication de la PL avant imagerie, image en cocarde à l'IRM de diffusion, ponction stéréotaxique + tri-antibiothérapie."},
    {"slug": "poss_neuro_adenome_apoplexie", "module_id": "neuro-neurochir", "sub_discipline": "Neurochirurgie", "course_hints": ["adénomes hypophysaires"], "focus": "Apoplexie hypophysaire aiguë (céphalée en coup de tonnerre, diplopie par atteinte III/VI, hémianopsie bitemporale, hyponatrémie) : hydrocortisone IV urgente avant tout bilan, décompression transsphénoïdale vs surveillance."},
    {"slug": "poss_neuro_myasthenie_crise", "module_id": "neuro-neurochir", "sub_discipline": "Neurologie", "course_hints": ["myasthénie"], "focus": "Crise myasthénique aiguë déclenchée par une prise d'antibiotique contre-indiqué (aminoside/fluoroquinolone) ou bêtabloquant : ptosis fluctuant, dysphagie, dyspnée, décrément à 3 Hz, anticorps anti-RACh/anti-MuSK, réanimation + IgIV/échanges plasmatiques."},
]


def _call_gemini(
    parts: list[dict[str, Any]],
    models: list[str],
    temperature: float = 0.2,
    timeout: int = 45,
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
                            _COOLDOWN_UNTIL[model] = time.time() + 20.0
                    elif he.code in (500, 502, 503, 504):
                        _COOLDOWN_UNTIL[model] = time.time() + 10.0
                continue
            except Exception as exc:
                last_err = exc
                with _MODEL_LOCK:
                    _COOLDOWN_UNTIL[model] = time.time() + 15.0
                continue
        time.sleep(3.0 * (attempt + 1))
    raise RuntimeError(f"Gemini call failed: {last_err}")


def _sample_pdf_jpegs(pdf_path: Path, max_pages: int = 8) -> list[bytes]:
    """Render evenly sampled pages of a scanned PDF as compact JPEG bytes."""
    import pypdf

    try:
        n_pages = len(pypdf.PdfReader(str(pdf_path)).pages)
    except Exception:
        n_pages = 8
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
    """Assemble full text, shared course docs, professor corpora, and/or sampled scanned page JPEGs."""
    cid = course_row["id"]
    c_title_norm = norm(course_row["canonical_title"])

    files = list(
        conn.execute(
            """
            SELECT id, name, category, local_path, text_chars, page_count, version_tag
            FROM drive_files
            WHERE course_id = ? AND local_path IS NOT NULL
            ORDER BY CASE WHEN category='cours' THEN 0 WHEN category='resume_mohamed' THEN 1 ELSE 2 END,
                     CASE WHEN version_tag='2026-2027' THEN 0 WHEN version_tag='final' THEN 1 ELSE 2 END,
                     text_chars DESC
            """,
            (cid,),
        ).fetchall()
    )

    # Fallback / supplement from shared multi-chapter course files & Professor QE/Exam corpora
    if not files:
        matched_names: list[str] = []
        for title_key, doc_patterns in SHARED_COURSE_DOC_MAP:
            if title_key in c_title_norm:
                matched_names.extend(doc_patterns)
        for pat in matched_names:
            extra = conn.execute(
                """
                SELECT id, name, category, local_path, text_chars, page_count, version_tag
                FROM drive_files
                WHERE local_path IS NOT NULL AND name LIKE ?
                ORDER BY text_chars DESC LIMIT 2
                """,
                (f"%{pat}%",),
            ).fetchall()
            files.extend(extra)

    text_blocks: list[str] = []
    image_parts: list[dict[str, Any]] = []
    doc_names: list[str] = []
    scanned_pdfs: list[Path] = []
    seen_ids: set[str] = set()

    for f in files:
        if f["id"] in seen_ids:
            continue
        seen_ids.add(f["id"])
        lp = DATA_DIR / f["local_path"]
        if not lp.exists():
            continue
        doc_names.append(f["name"])
        tchars, _, txt = extract_full_text(lp, max_chars=24000)
        if tchars >= 300 and txt:
            if sum(len(b) for b in text_blocks) < 26000:
                text_blocks.append(f"=== DOCUMENT [{f['category']}] : {f['name']} ===\n{txt[:18000]}")
        elif f["name"].lower().endswith(".pdf"):
            scanned_pdfs.append(lp)

    # Also include course high_yield_points and existing annales (questions + explanations) as context
    hy_raw = course_row["high_yield_points"] if "high_yield_points" in course_row.keys() else "[]"
    try:
        hy_list = json.loads(hy_raw or "[]")
    except Exception:
        hy_list = []
    if hy_list:
        text_blocks.append("=== POINTS HAUT RENDEMENT DU COURS ===\n" + "\n".join(f"- {b}" for b in hy_list[:20]))

    annale_rows = conn.execute(
        """
        SELECT stem, options_json, correct_answers_json, explanation, source_label
        FROM questions
        WHERE course_id = ? AND COALESCE(is_predicted, 0) = 0
        LIMIT 15
        """,
        (cid,),
    ).fetchall()
    existing_qs = [r["stem"] for r in annale_rows]
    if annale_rows:
        ann_lines = []
        for r in annale_rows[:10]:
            ann_lines.append(f"• [{r['source_label']}] {r['stem']} | Explication: {r['explanation'][:220]}")
        text_blocks.append("=== ANNALES OFFICIELLES DE CE CHAPITRE (POUR CALIBRER LE NIVEAU SANS RECOPIER) ===\n" + "\n".join(ann_lines))

    # Render scanned pages only if total text across all files is thin (< 1500 chars)
    if sum(len(b) for b in text_blocks) < 1500 and scanned_pdfs:
        per_pdf = max(4, 8 // len(scanned_pdfs))
        for spdf in scanned_pdfs[:2]:
            for jb in _sample_pdf_jpegs(spdf, max_pages=per_pdf):
                image_parts.append({
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": base64.b64encode(jb).decode("ascii"),
                    }
                })

    if not doc_names:
        doc_names = [f"Syllabus FMPO S7 · {course_row['canonical_title']} ({course_row['professor']})"]

    return {
        "doc_names": doc_names,
        "combined_text": "\n\n".join(text_blocks)[:28000],
        "image_parts": image_parts[:8],
        "existing_stems": existing_qs,
        "has_real_docs": True,
    }


def _is_combo_or_trivial_option(t: str) -> bool:
    s = t.strip()
    if len(s) < 20:
        return True
    if re.match(r"^[A-Ea-e1-5](\s*[,;+\-et/&]\s*[A-Ea-e1-5])+\.?$", s):
        return True
    low = s.lower()
    for banned in (
        "toutes les propositions",
        "toutes les réponses",
        "aucune des propositions",
        "aucune réponse",
        "propositions ci-dessus",
        "réponses a et",
        "réponses b et",
    ):
        if banned in low:
            return True
    return False


def _normalize_letter_items(items: Any, lowercase: bool = False) -> list[dict[str, str]]:
    """Coerce Gemini statement/option lists cleanly into [{letter, text}]."""
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
    """Strictly validate every generated question so zero malformed or weak items ever pass."""
    if not isinstance(q, dict):
        return None
    qtype = str(q.get("question_type", "qcm_multi")).strip()
    if qtype not in ("qcm_multi", "qcm_group", "qroc"):
        return None
    stem = str(q.get("stem") or "").strip()
    explanation = str(q.get("explanation") or "").strip()
    if len(stem) < 28 or len(explanation) < 55:
        return None

    stmts = _normalize_letter_items(q.get("statements") or [], lowercase=True)
    opts = _normalize_letter_items(q.get("options") or [], lowercase=False)
    corr = [str(x).strip().upper()[:2] for x in (q.get("correct_answers") or []) if str(x).strip()]
    rubric = [str(x).strip() for x in (q.get("rubric_points") or []) if len(str(x).strip()) >= 10]

    # Rescue mislabeled qcm_group (where statements has 5 full sentences and options has letter combos)
    if qtype == "qcm_multi" and len(stmts) >= 4 and len(opts) >= 4:
        if all(len(s["text"]) >= 20 for s in stmts) and any(len(o["text"]) < 20 for o in opts) and len(corr) == 1:
            qtype = "qcm_group"

    if qtype == "qcm_group":
        if len(stmts) < 4 or len(opts) < 4 or len(corr) != 1:
            return None
        if any(len(s["text"].strip()) < 22 for s in stmts):
            return None
        valid_letters = {o["letter"] for o in opts}
        if corr[0] not in valid_letters:
            return None
    elif qtype == "qcm_multi":
        if len(opts) < 5 or not corr or len(corr) > 4:
            return None
        if any(_is_combo_or_trivial_option(o["text"]) for o in opts):
            return None
        valid_letters = {o["letter"] for o in opts}
        corr = [x for x in corr if x in valid_letters]
        if not corr:
            return None
        stmts = []
    elif qtype == "qroc":
        if len(rubric) < 3:
            return None
        stmts, opts, corr = [], [], []

    tier = str(q.get("difficulty_tier") or "wa3ra").strip().lower()
    if tier not in ("piege_jury", "wa3ra"):
        tier = "wa3ra"
    try:
        score = max(78, min(99, int(q.get("likelihood_score") or 88)))
    except Exception:
        score = 88

    return {
        "question_type": qtype,
        "vignette_text": str(q.get("vignette_text")).strip() if q.get("vignette_text") else None,
        "stem": stem,
        "statements": stmts[:5],
        "options": opts[:5],
        "correct_answers": corr,
        "rubric_points": rubric[:5],
        "difficulty_tier": tier,
        "likelihood_score": score,
        "doc_evidence": str(q.get("doc_evidence") or default_doc).strip()[:400],
        "explanation": explanation,
    }


def _question_prompt(c_row, ctx: dict[str, Any], target_count: int, existing_clean_stems: list[str]) -> str:
    mod_id = c_row["module_id"]
    if mod_id == "anapath":
        fmt_rule = (
            "Génère des 'qcm_multi' (et au maximum 1 ou 2 'qcm_group') de niveau Concours d'Internat / Examen FMPO. "
            "Cible les marqueurs immunohistochimiques (TTF1, p40, CD20, CD30, CD15, HER2, CD117, PAX8, E-cadhérine...), "
            "les critères morphologiques pathognomoniques, les grades histopronostiques (SBR, ISUP, Lauren, OLGA) et les règles d'examen extemporané/fixation."
        )
    elif mod_id == "neuro-neurochir":
        fmt_rule = (
            "Génère 2 questions rédactionnelles 'qroc' (avec `rubric_points` contenant 4 critères précis attendus au barème) "
            "et le reste en 'qcm_multi' cliniques/paracliniques exigeants (imagerie TDM/IRM, LCR, ENMG, urgences neurochirurgicales, contre-indications)."
        )
    else:
        fmt_rule = (
            "Génère UNIQUEMENT des 'qcm_multi' à 5 propositions autonomes A..E (2 à 4 réponses exactes) de niveau Examen National / Jury FMPO. "
            "Privilégie les mini-vignettes cliniques chiffrées, les seuils biologiques exacts, les diagnostics différentiels piégeux et les contre-indications thérapeutiques."
        )

    all_avoid = (ctx["existing_stems"] + existing_clean_stems)[:14]
    existing_block = "\n".join(f"- {s}" for s in all_avoid) or "Aucune question existante."
    docs_list = ", ".join(ctx["doc_names"][:3])

    return f"""Tu es Professeur Agrégé et membre du jury d'examen de 4e année de Médecine (Semestre 7, FMPO Oujda).
Rédige EXACTEMENT {target_count} questions d'examen de TRÈS HAUTE QUALITÉ PROFESSIONNELLE (« questions wa3rin & pièges du jury ») sur le chapitre suivant :
- Module : {c_row['module_id']} ({c_row['sub_discipline']})
- Chapitre : {c_row['canonical_title']}
- Professeur responsable : {c_row['professor']}
- Supports analysés : {docs_list}

Questions déjà existantes (NE PAS LES RECOPIER — couvre d'autres axes cliniques, seuils, formes graves ou pièges thérapeutiques du cours) :
{existing_block}

CONSIGNES DOCIMOLOGIQUES STRICTES (ZÉRO QUESTION SUPERFICIELLE OU MAL FORMÉE) :
{fmt_rule}
1. Pour `qcm_multi` :
   - `statements` DOIT être `[]` (vide).
   - `options` DOIT contenir exactement 5 objets `A`, `B`, `C`, `D`, `E`.
   - **INTERDICTION ABSOLUE** de mettre des combinaisons de lettres (`"A, B, C"`, `"a ; b ; c"`, `"Toutes les réponses sont justes"`) dans `options` !
   - **CHAQUE option `A` à `E` DOIT être une proposition médicale complète, précise et autonome d'au moins 12 à 25 mots** (ex: `{{"letter": "A", "text": "La présence d'une hypokaliémie inférieure à 3,3 mmol/L contre-indique formellement le démarrage immédiat de l'insulinothérapie IV avant supplémentation potassique."}}`).
   - `correct_answers` contient les lettres exactes vraies (ex: `["A", "C", "E"]`).
2. Pour `qcm_group` (Anatomopathologie uniquement) :
   - `statements` contient 5 propositions complètes `a` à `e` (chacune >= 12 mots, JAMAIS un mot isolé !).
   - `options` contient 5 combinaisons `A` à `E` (ex: `{{"letter": "A", "text": "a, c, d"}}`) et `correct_answers` contient 1 seule lettre `["A"]`.
3. Pour `qroc` :
   - `statements: []`, `options: []`, `correct_answers: []`, et `rubric_points` contient 4 critères précis complets attendus par le correcteur.
4. `explanation` DOIT être une correction médicale professionnelle et détaillée (>= 90 mots) structurée ainsi :
   "• A (Vrai/Faux) : justification précise... • B (Vrai/Faux) : ... • C (Vrai/Faux) : ... • D (Vrai/Faux) : ... • E (Vrai/Faux) : ... | Réflexe Jury FMPO : règle d'or à retenir."
5. `doc_evidence` : cite le support exact et la section (ex: `"{docs_list} — Diagnostic & Prise en charge"`).

Réponds UNIQUEMENT en JSON strict :
{{
  "questions": [
    {{
      "question_type": "qcm_multi",
      "vignette_text": "Patiente de 42 ans admise aux urgences pour... (ou null si question docimologique directe)",
      "stem": "Concernant le diagnostic positif et la prise en charge de cette patiente, quelles sont les propositions exactes ?",
      "statements": [],
      "options": [
        {{"letter": "A", "text": "Phrase médicale complète et rigoureuse numéro 1..."}},
        {{"letter": "B", "text": "Phrase médicale complète et rigoureuse numéro 2..."}},
        {{"letter": "C", "text": "Phrase médicale complète et rigoureuse numéro 3..."}},
        {{"letter": "D", "text": "Phrase médicale complète et rigoureuse numéro 4..."}},
        {{"letter": "E", "text": "Phrase médicale complète et rigoureuse numéro 5..."}}
      ],
      "correct_answers": ["A", "C", "D"],
      "rubric_points": [],
      "difficulty_tier": "piege_jury",
      "likelihood_score": 94,
      "doc_evidence": "{docs_list} — Section ...",
      "explanation": "• A (Vrai) : ... • B (Faux) : piège classique car... • C (Vrai) : ... • D (Vrai) : ... • E (Faux) : ... | Réflexe Jury FMPO : ..."
    }}
  ]
}}

CONTENU DU COURS ET DES SUPPORTS :
{ctx['combined_text']}
"""


def _build_case_prompt(bp: dict[str, Any], matched_courses: list[dict[str, Any]], combined_text: str, doc_names: list[str]) -> str:
    c_summary = ", ".join(f"{c['canonical_title']} ({c['professor']})" for c in matched_courses) or bp["sub_discipline"]
    return f"""Tu es professeur chef de service clinique à la FMPO d'Oujda. Rédige UN cas clinique progressif de TRÈS HAUT NIVEAU (« cas clinique nadi & sélectif ») en 4 étapes cohérentes.

Cible :
- Module : {bp['module_id']} / {bp['sub_discipline']}
- Cours associés : {c_summary}
- Documents analysés : {', '.join(doc_names) or 'Programme S7 FMPO'}
- Axe clinique précis : {bp['focus']}

Exigences cliniques strictes :
1. `patient_summary` : présentation réaliste aux urgences du CHU Mohammed VI d'Oujda ou en consultation spécialisée (âge, terrain, antécédents, chronologie horaire exacte, prise médicamenteuse éventuelle créant un piège).
2. `vitals_json` : exactement 5 à 6 constantes chiffrées pertinentes (ex: PA, FC, SpO2, T°, Glycémie ou marqueur clé).
3. `steps_json` : EXACTEMENT 4 étapes progressives :
   - Step 1 (`diagnosis`) : Raisonnement diagnostique et piège sémiologique/étiologique. Format `"qcm_multi"`, 5 options A..E complètes (>= 12 mots chacune, `2` ou `3` exactes).
   - Step 2 (`workup_choice`) : Bilan paraclinique hiérarchisé (avec distracteurs piégeux : examen contre-indiqué, retardateur ou faussement rassurant). Format `"qcm_multi"`, 5 options A..E complètes.
   - Step 3 (`management`) : Conduite thérapeutique immédiate, posologie/voie ou ordre critique avant autre geste. Format `"qcm_multi"`, 5 options A..E complètes.
   - Step 4 (`complication` ou `synthesis`) : Évolution aiguë à H+6/J+4 ou critère pronostique/anatomopathologique décisionnel. Format `"qcm_multi"`, 5 options A..E complètes.
4. Chaque étape doit contenir :
   - `clinical_reveal`: résultat clinique ou biologique chiffré réaliste dévoilé à cette étape.
   - `red_flags`: 2 pièges fatals concrets à ne jamais commettre.
   - `teaching_pearl`: perle de synthèse rigoureuse façon jury FMPO.
   - `points`: 2.
5. `takeaway_points`: 4 réflexes d'or finaux à retenir pour l'examen S7.
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
      "red_flags": ["...", "..."],
      "teaching_pearl": "...",
      "points": 2
    }}
  ],
  "takeaway_points": ["...", "...", "...", "..."],
  "doc_evidence": "..."
}}

EXTRAITS DES DOCUMENTS DE COURS ANALYSÉS :
{combined_text[:26000]}
"""


def _validate_case(raw: dict[str, Any], bp: dict[str, Any], course_id: int | None) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
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
        if any(len(o["text"]) < 12 for o in opts):
            return None
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
            "options": opts[:5],
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

    # 0. Audit & purge any previously cached malformed questions so only 100% professional questions remain
    purged_total = 0
    kept_total = 0
    for cid_str, entry in list(cache["courses"].items()):
        default_doc = ", ".join(entry.get("doc_names") or []) or entry.get("course_title", "")
        valid_qs = []
        for q in entry.get("questions", []):
            vq = _validate_question_item(q, default_doc)
            if vq:
                valid_qs.append(vq)
            else:
                purged_total += 1
        entry["questions"] = valid_qs
        kept_total += len(valid_qs)
    print(f"Cache audit: kept {kept_total} strictly valid professional questions, purged {purged_total} malformed/weak questions.")
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2))

    # 1. Select ALL 113 real courses in S7 syllabus
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
    course_jobs: list[tuple[dict[str, Any], dict[str, Any], int, list[dict[str, Any]]]] = []
    for c in courses:
        cid_str = str(c["id"])
        ctx = _gather_course_context(conn, c)
        contexts_by_cid[c["id"]] = ctx
        existing_clean = cache["courses"].get(cid_str, {}).get("questions", [])
        # Target 5 questions for priority/0-annale courses, 4 for standard courses; if < 4 clean questions exist, generate 5 new ones
        desired_min = 4
        if len(existing_clean) < desired_min:
            need = max(4, 5 - len(existing_clean))
            course_jobs.append((dict(c), ctx, need, existing_clean))

    print(f"Total real S7 courses: {len(courses)} | Courses needing professional generation/repair: {len(course_jobs)}")

    def _run_course_job(job: tuple[int, dict[str, Any], dict[str, Any], int, list[dict[str, Any]]]) -> tuple[str, dict[str, Any]]:
        j_idx, c_row, ctx, n_target, existing_clean = job
        existing_stems = [q["stem"] for q in existing_clean]
        default_doc = ", ".join(ctx["doc_names"][:2]) if ctx["doc_names"] else c_row["canonical_title"]
        accumulated = list(existing_clean)

        for pass_num in range(2):
            still_needed = max(4, n_target) - len(accumulated)
            if still_needed <= 0:
                break
            ask_cnt = max(4, still_needed + 1)
            prompt = _question_prompt(c_row, ctx, ask_cnt, [q["stem"] for q in accumulated])
            parts: list[dict[str, Any]] = [{"text": prompt}] + ctx["image_parts"]
            res = _call_gemini(parts, MODELS_QUESTIONS, temperature=0.22 + pass_num * 0.08, timeout=45, rotate_idx=j_idx + pass_num)
            seen_stems = {norm(q["stem"]) for q in accumulated}
            for q in (res.get("questions") or []):
                vq = _validate_question_item(q, default_doc)
                if vq and norm(vq["stem"]) not in seen_stems:
                    accumulated.append(vq)
                    seen_stems.add(norm(vq["stem"]))

        return str(c_row["id"]), {
            "course_title": c_row["canonical_title"],
            "module_id": c_row["module_id"],
            "sub_discipline": c_row["sub_discipline"],
            "professor": c_row["professor"],
            "annale_cnt": c_row["annale_cnt"],
            "doc_names": ctx["doc_names"],
            "questions": accumulated,
        }

    if course_jobs:
        numbered_jobs = [(i, c_row, ctx, n_target, ex) for i, (c_row, ctx, n_target, ex) in enumerate(course_jobs)]
        with ThreadPoolExecutor(max_workers=4) as pool:
            futs = [pool.submit(_run_course_job, j) for j in numbered_jobs]
            for idx, fut in enumerate(as_completed(futs), 1):
                try:
                    cid_str, entry = fut.result()
                    with _MODEL_LOCK:
                        cache["courses"][cid_str] = entry
                        CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
                    print(f"  [{idx}/{len(course_jobs)}] OK {entry['module_id']} · {entry['course_title']} -> {len(entry['questions'])} pro Qs ({', '.join(entry['doc_names'][:2])})")
                except Exception as exc:
                    print(f"  [{idx}/{len(course_jobs)}] ERR: {exc}")

    # 2. Generate showcase Complex Clinical Cases (30 total)
    pending_bps = [bp for bp in COMPLEX_CASE_BLUEPRINTS if bp["slug"] not in cache["cases"] or not cache["cases"].get(bp["slug"])]
    print(f"Generating {len(pending_bps)} new complex multi-step clinical cases...")

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
        case_jobs.append((bp, matched, "\n\n".join(text_parts), list(dict.fromkeys(doc_names)), image_parts[:6]))

    def _run_case_job(cjob: tuple[int, dict[str, Any], list[dict[str, Any]], str, list[str], list[dict[str, Any]]]) -> tuple[str, dict[str, Any] | None]:
        c_idx, bp, matched, combined_text, doc_names, image_parts = cjob
        prompt = _build_case_prompt(bp, matched, combined_text, doc_names)
        parts: list[dict[str, Any]] = [{"text": prompt}] + image_parts
        raw = _call_gemini(parts, MODELS_CASES, temperature=0.25, timeout=55, rotate_idx=c_idx)
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
    covered_courses = 0
    for cid_str, entry in sorted(cache["courses"].items(), key=lambda x: int(x[0])):
        cid = int(cid_str)
        qs_list = entry.get("questions") or []
        if not qs_list:
            continue
        covered_courses += 1
        ann_cnt = int(entry.get("annale_cnt") or 0)
        src_lbl = f"PRÉDICTION COURS · {entry['professor']}" if ann_cnt > 0 else f"PRÉDICTION HORS-ANNALES · {entry['professor']}"
        for idx, q in enumerate(qs_list, 1):
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
    print(f"\nCOMPLETE: Inserted {q_inserted} strictly validated Possible Questions across {covered_courses}/113 courses + {c_inserted} Complex Clinical Cases.")
    conn.close()


if __name__ == "__main__":
    main()
