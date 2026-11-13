#!/usr/bin/env python3
"""Populate data/drive_cache with existing local scratch files + high-yield courses & corrigés."""
import json
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CACHE_DIR = DATA_DIR / "drive_cache"
SCANS_DIR = DATA_DIR / "scans"
SCRATCH = Path("/home/kali/.gemini/antigravity/brain/904c8a03-aaf4-439d-bce1-177b59d16974/scratch")

CACHE_DIR.mkdir(parents=True, exist_ok=True)
SCANS_DIR.mkdir(parents=True, exist_ok=True)

# 1. Copy static metadata & rendered 2025 SN pages
shutil.copy2(SCRATCH / "full_inventory.json", DATA_DIR / "full_inventory.json")
shutil.copy2(SCRATCH / "S7_check_promo_2023_restructure.xlsx", DATA_DIR / "S7_check_promo_2023_restructure.xlsx")

sn_dest = SCANS_DIR / "sn2025"
sn_dest.mkdir(parents=True, exist_ok=True)
for png in (SCRATCH / "sn2025_pages").glob("*.png"):
    shutil.copy2(png, sn_dest / png.name)

inv = json.loads((DATA_DIR / "full_inventory.json").read_text())
files = {n["id"]: n for n in inv["nodes"] if n["kind"] == "file"}

# 2. Map already-downloaded scratch files into data/drive_cache/by_id/<id>/
EXISTING_MAP = {
    "1430zxH8EZgTdqpDAhLkXuupkVYy2FXHB": SCRATCH / "samples" / "1_LES_GASTRITES.pdf",
    "1mx4lD1Cyb39KNbV1NQkHde-lkVpMByz6": SCRATCH / "samples" / "CORRECTION_EXAMEN_BLANC_ENDOCRINO.pdf",
    "1txbPJHd7__WWGC94pdXuUWmVQYprxYzp": SCRATCH / "samples" / "CORRECTION_EXAMEN_BLANC_NEURO_2025.pdf",
    "1tgm61Hi81qVQ53XsTPF-MEkg--Ioglay": SCRATCH / "samples" / "Cours_transfusion.pdf",
    "1YCrIB6yJeDNI3nG_Z-xuBwBiGjRgBI6-": SCRATCH / "samples" / "cours_urgences_onco_2026.docx",
    "1T1pWkV6ULtUSjQ3QGYpwNHCSWOJ7xj0f": SCRATCH / "samples" / "EXAMEN_APS_2025_SN.pdf",
    "119qZS3jTZrtk6f0NB35innarXm-0Vute": SCRATCH / "samples" / "EXAMEN_BLANC_ENDOCRINO.pdf",
    "1tZanePTijMdq2R3oxDex5M_silBKW9pv": SCRATCH / "samples" / "EXAMEN_BLANC_NEURO_2025.pdf",
    "1ut6iSVe76R34C0W5bGo7c9r1jCvwVj-f": SCRATCH / "samples" / "EXAMEN_DERMATO_2025_SN.pdf",
    "1uEU_UaRXMvOWzLKHyg6H10ZFeWgkKpvd": SCRATCH / "samples" / "EXAMEN_ENDOCRINO_2025_SN.pdf",
    "1LXR57TSN4JpH0cAsTnsNJEomz4i8H-CC": SCRATCH / "samples" / "EXAMEN_HEMATO_ONCO_2025_SN.pdf",
    "1yDIe_04crG9EVyK8GE9sXZjyLVNom2kw": SCRATCH / "samples" / "EXAMEN_NEURO_NEUROCHIR_2025_SN.pdf",
    "1IVE5BymfRFM6IIaT7CObpbZ3QJ-c3ZtQ": SCRATCH / "samples" / "Hemorragie_meningee.pptx",
    "1O2qyMolbdkUizXot6nOFDZIR34vwcuWe": SCRATCH / "samples" / "HVP_FMPO_FINAL.pdf",
    "1f7TRdM97oowh8dtgzQirS6QkuFv9skxy": SCRATCH / "samples" / "HVP_FMPO_plus.pdf",
    "1Sy6SAYrC8g_rsRAm3oIPVgySFySa8UBn": SCRATCH / "samples" / "hypoglycemie_non_dt_2026.pdf",
    "1NB9NpNtr0nTjfPOWh8UKccAWE1w4MV7L": SCRATCH / "samples" / "Mohamed_R_behcet.pdf",
    "1QYDwNCCX-hetHgJYwtNq36sh787sVg2g": SCRATCH / "samples" / "QE_ECN_DERMATO_P1_C.pdf",
    "1mPjHMNODborv18kXCSBRtozWeRclySZX": SCRATCH / "samples" / "QE_PR_ALAOUI_NC.pdf",
    "14gHFBdyMUjFohx5O8gJyYaSKyqGfAWn6": SCRATCH / "samples" / "QE_PR_BENNANI_C.pdf",
    "1yGHzCiR2Anopl8X4Y0FXFDj5LcY-wDJ4": SCRATCH / "samples" / "QE_PR_BENNANI_NC.pdf",
    "1ydeIVCnonlGbG1-LPzYt77WcQbdJ2gBe": SCRATCH / "samples" / "QE_PR_KHOULALI_C.pdf",
    "1g4HxQZSRbCUazoNsTy6whjPJijdWJzdN": SCRATCH / "samples" / "QE_PR_KHOULALI_NC.pdf",
    "1XI8GGNhnNstdg2CWtynGEoZl5v9970yi": SCRATCH / "samples" / "QE_PR_ROUF_C.pdf",
    "1rUXKkEwgC8Go8GSrZ_1xyPhcgsXgqx61": SCRATCH / "samples" / "QE_PR_ROUF_NC.pdf",
    "1YYWiuY2fKL-WC7ipbgtXzF-jp3zO0zg-": SCRATCH / "samples" / "QUIZ_Amphi_Dermato.pdf",
    "1sE0PUVp1WkPtVxt0M1feq4k4imRAd8Rt": SCRATCH / "samples" / "Share_waldenstrom.pptx",
    "1bcVvvV-YkXhu-6bvkMCxvTtQXX6DpS4u": SCRATCH / "samples" / "Syphilis_2026_2027.pdf",
    "1JBHlz-tz3T8zzvqWp7IvyxRhkMvK9Dm-": SCRATCH / "samples" / "urgences_onco_2026.pdf",
    "1-5fSuECd8VLN2ZWjEeYvyo4a6aef7Nbj": SCRATCH / "qes" / "QE_ECN_DERMATO_P1_NC.pdf",
    "1nfih9QiR1neqeVTPxsvBOl0Y2SC3xsma": SCRATCH / "qes" / "QE_ECN_DERMATO_P2_C.pdf",
    "1MqnX43_pk2ua2i7EXlP-0zscp_xEqnq0": SCRATCH / "qes" / "QE_ECN_DERMATO_P2_NC.pdf",
    "1WJUBqDet1y8K0n23AwxfUa6D8pdMJwZO": SCRATCH / "qes" / "QE_PR_AFAIK_NC.pdf",
    "12Y_SqtS5Nhp8HHsL3zMKxCi8pORUbM5f": SCRATCH / "qes" / "QE_PR_BOUICHRAT_NC.pdf",
    "1RJaOXtl_4Ydc1ogIfpVzKaGwNKOZCVOL": SCRATCH / "qes" / "QE_PR_HALAOUI_NC.pdf",
    "1b-9h3hs9v7WdXFMsHQCSk-2t-AC3ec9U": SCRATCH / "qes" / "QE_PR_HAMAZ_NC.pdf",
    "1tZrDWg1nkQ3o2mZuvcpl7qWCoC-4AlmE": SCRATCH / "qes" / "QE_PR_KARICH_NC.pdf",
    "1Pq7HDAtpaK5w6WTEMJ9xAYNJcFDO-bWL": SCRATCH / "qes" / "QE_PR_LATRECH_NC.pdf",
    "1xj349fourhxFRAvo4-kwjXHu9rxN417y": SCRATCH / "qes" / "QE_PR_MEZOUAR_NC.pdf",
    "1EFsEiSuiY4KTjsc2ZA1R4dDHZF9iwLgr": SCRATCH / "qes" / "QE_PR_SADKI_NC.pdf",
    "15YD_9MCPCVh-HqKARwyKbCvPhxWiBwkO": SCRATCH / "qes" / "QE_PR_SERJI_NC.pdf",
    "1FQ0z_L969V8ctOTnu9jRLvWpff7MevSc": SCRATCH / "qes" / "QE_PR_SERRAJ_NC.pdf",
}

copied = 0
for fid, src in EXISTING_MAP.items():
    if fid in files and src.exists():
        dest = CACHE_DIR / "by_id" / fid / files[fid]["name"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            shutil.copy2(src, dest)
            copied += 1
print(f"Copied {copied} already-cached files.")

# 3. Select high-yield missing files (all small/medium courses <= 16MB, key NeuroChir PPTX, remaining small/medium CORRIGES, PROGRAMME)
to_download = []
for fid, f in files.items():
    dest = CACHE_DIR / "by_id" / fid / f["name"]
    if dest.exists():
        continue
    p = f["path"]
    sz = f.get("size", 0)
    is_course = ("/Cours/" in p or "Neurologie/" in p or "Neurochirurgie/" in p or "Endocrino /" in p or "Dermato/" in p or "Hematologie/" in p or "Oncologie/" in p) and "/Résumé /" not in p
    is_corrige_med = "/CORRIGÉS/" in p and sz <= 18_000_000
    is_programme = "PROGRAMME S7" in p
    is_key_large = fid == "1KI8Tz-2lbOQNZ8fimspzCQ2ALunF-P5i"  # Spondylodiscites 2026-2027 (tested in 2025 SN)
    is_mohamed_med = "/Résumer Mohamed jrh /" in p and sz <= 10_000_000
    if (is_course and sz <= 16_000_000) or is_corrige_med or is_programme or is_key_large or is_mohamed_med:
        to_download.append((fid, f["name"], dest, sz))

print(f"Downloading {len(to_download)} high-yield files totaling {sum(x[3] for x in to_download)/1e6:.1f} MB...")

def dl(item):
    fid, name, dest, _ = item
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    cmd = ["gdrive", "readonly", "download", fid, "--out", str(tmp)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 and tmp.exists():
        tmp.rename(dest)
        return (fid, name, True, "")
    return (fid, name, False, res.stderr.strip() or res.stdout.strip())

ok = fail = 0
with ThreadPoolExecutor(max_workers=6) as ex:
    futs = [ex.submit(dl, item) for item in to_download]
    for fut in as_completed(futs):
        fid, name, success, err = fut.result()
        if success:
            ok += 1
        else:
            fail += 1
            print(f"FAIL {name}: {err}")
print(f"Download complete: {ok} succeeded, {fail} failed.")
