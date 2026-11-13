# FMPO S7 MedPrep Studio

Plateforme personnelle de préparation aux examens et situations cliniques du **Semestre 7 (4ème année Médecine, FMPO Oujda)**, bâtie directement sur votre dépôt Google Drive S7.

## Lancement rapide

```bash
cd frontend && npm install && npm run build && cd ..
./start.sh
```

Puis ouvrez [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Architecture

- `backend/` : API FastAPI + SQLite (`data/s7_platform.db`), notation exacte des 4 formats FMPO (`qcm_multi`, `qcm_group` A–E, `qroc`/`synthesis` à grille de mots-clés), planification espacée, téléchargement Drive à la demande.
- `pipeline/` : Scripts d'ingestion du programme (`S7_check_promo_2023_restructure.xlsx`), indexation des 166 fichiers Drive, numérisation OCR Vision des épreuves scannées 2025 SN (`aps`, `endo`, `derm`, `hemato`, `neuro`), extraction par détection RGB des surlignages vert/jaune sur les corrigés annotés, et situations cliniques.
- `frontend/` : Interface React + TypeScript + Tailwind v4 servie directement par FastAPI depuis `frontend/dist/`.

## Déploiement Cloud (Docker / Railway / Render / Fly.io)

Le `Dockerfile` multi-étage compile le frontend Vite, installe `poppler-utils` et les dépendances Python (`requirements.txt`), puis amorce automatiquement un volume persistant monté sur `/app/data` depuis `/app/seed_data`.

### Variables d'environnement optionnelles

- `PORT` : Port HTTP d'écoute (défaut `8000`).
- `S7_DATA_DIR` : Répertoire des données et SQLite (défaut `/app/data` dans Docker).
- `APP_ACCESS_PASSWORD` : Active un verrouillage HTTP Basic Auth sur toute l'application (hors `/api/health`) lorsqu'elle est exposée publiquement.
- `APP_ACCESS_USER` : Identifiant Basic Auth associé (défaut `medprep`).
- `GEMINI_API_KEY` : Requis uniquement pour exécuter l'extraction OCR Vision en direct dans le Studio Scans.
