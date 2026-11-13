#!/usr/bin/env python3
"""Seed interactive multi-step Clinical Situations across all 4 S7 FMPO modules."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.db import DB_PATH, get_conn, init_db  # noqa: E402
from pipeline.ingest_inventory import token_score  # noqa: E402

CASES = [
    {
        "slug": "neuro_avci_thrombolyse_triage",
        "module_id": "neuro-neurochir",
        "sub_discipline": "Neurologie",
        "course_hint": "AVCI",
        "title": "Urgence neurovasculaire : déficit brutal du membre inférieur gauche et décision de thrombolyse",
        "difficulty": "Élevée",
        "source_tag": "EXAMEN 2025 SN + Cours AVCI Pr Mabrouk",
        "patient_summary": "Homme de 64 ans, hypertendu mal suivi et diabétique sous metformine, amené aux urgences à 10h30 pour un déficit moteur brutal du membre inférieur droit et des troubles comportementaux débutés à 8h45. Pas de traumatisme crânien.",
        "vitals_json": {"PA": "195/105 mmHg", "FC": "98 bpm irrégulière", "Glycémie capillaire": "1,45 g/L", "SpO2": "97%", "T°": "36,9 °C", "NIHSS": "9"},
        "steps_json": [
            {
                "step_number": 1,
                "step_type": "diagnosis",
                "prompt": "Cliniquement, la prédominance crurale du déficit moteur droit avec troubles frontaux et réflexe de préhension évoque une atteinte de quel territoire artériel ?",
                "clinical_reveal": "Examen neurologique : parésie crurale droite (membre inférieur 1/5, membre supérieur 4/5, face épargnée), apraxie idéomotrice, incontinence urinaire et mutisme akinétique partiel.",
                "question_format": "qcm_multi",
                "options": [
                    {"letter": "A", "text": "Artère cérébrale antérieure (ACA) gauche"},
                    {"letter": "B", "text": "Artère cérébrale moyenne (ACM) superficielle gauche"},
                    {"letter": "C", "text": "Artère cérébrale postérieure gauche"},
                    {"letter": "D", "text": "Tronc basilaire"},
                    {"letter": "E", "text": "Syndrome alterne de Wallenberg"}
                ],
                "correct_answers": ["A"],
                "red_flags": ["Confondre la prédominance crurale (ACA) avec la prédominance brachio-faciale (ACM superficielle)."],
                "teaching_pearl": "Occlusion de l'ACA gauche (question tombée à l'Examen 2025 SN !) : hémiplégie à prédominance crurale controlatérale, syndrome frontal (grasping, troubles sphinctériens) et troubles praxiques/du langage.",
                "points": 2
            },
            {
                "step_number": 2,
                "step_type": "workup_choice",
                "prompt": "Quel(s) examen(s) réalisez-vous en première intention en urgence avant toute décision de recanalisation ?",
                "clinical_reveal": "Délai écoulé depuis le début des symptômes : 1h45 (fenêtre < 4h30). ECG réalisé en box d'accueil : fibrillation auriculaire à 98 bpm.",
                "question_format": "qcm_multi",
                "options": [
                    {"letter": "A", "text": "IRM cérébrale en urgence (ou TDM cérébrale sans injection si IRM indisponible)"},
                    {"letter": "B", "text": "Glycémie capillaire et glycémie veineuse + bilan d'hémostase (TP, TCA, plaquettes)"},
                    {"letter": "C", "text": "Ponction lombaire systématique"},
                    {"letter": "D", "text": "Écho-Doppler des TSA avant l'imagerie cérébrale"},
                    {"letter": "E", "text": "Angioscanner des troncs supra-aortiques et du polygone de Willis"}
                ],
                "correct_answers": ["A", "B", "E"],
                "red_flags": ["Perdre du temps avec un Doppler des TSA avant l'imagerie parenchymateuse."],
                "teaching_pearl": "Tout déficit neurologique brutal impose en urgence une imagerie cérébrale (IRM avec séquences Diffusion/FLAIR/T2*/TOF ou TDM sans injection pour éliminer une hémorragie) + biologie minimale (glycémie immédiate + plaquettes/hémostase).",
                "points": 2
            },
            {
                "step_number": 3,
                "step_type": "management",
                "prompt": "La TDM sans injection élimine une hémorragie cérébrale. Avant d'administrer la thrombolyse IV (altéplase), quelle(s) action(s) ou vérification(s) impérative(s) s'impose(nt) chez ce patient à PA = 195/105 mmHg ?",
                "clinical_reveal": "Biologie : Plaquettes 220 000/mm³, TP 88%, TCA ratio 1,0, HbA1c 7,2%. Pas d'ATCD d'AVC ni de chirurgie récente.",
                "question_format": "qcm_multi",
                "options": [
                    {"letter": "A", "text": "Abaisser prudemment la PA sous 185/110 mmHg (nicardipine ou labétalol IV) car PA > 185/110 contre-indique la thrombolyse"},
                    {"letter": "B", "text": "Thrombolyser immédiatement sans toucher à la PA"},
                    {"letter": "C", "text": "Contre-indiquer définitivement la thrombolyse en raison de l'âge (64 ans)"},
                    {"letter": "D", "text": "Prévoir une anticoagulation curative immédiate par héparine avant la 24e heure sur l'AVCI"},
                    {"letter": "E", "text": "Introduction ultérieure d'un anticoagulant oral (AOD/AVK) en prévention secondaire vu la FA (après contrôle scan à 24h)"}
                ],
                "correct_answers": ["A", "E"],
                "red_flags": ["Débuter la thrombolyse IV alors que PA > 185/110 mmHg expose à une transformation hémorragique fatale.", "Ne pas confondre ATCD d'AVC + diabète (CI classique FMPO Examen Blanc) avec un premier AVC chez un diabétique."],
                "teaching_pearl": "Rappel Examen 2025 SN & Exam Blanc : PA > 185/110 mmHg est une contre-indication formelle tant qu'elle n'est pas maîtrisée en douceur. Autres CI clés : glycémie < 0,5 ou > 4 g/L, ATCD AVC hémorragique, AVC < 3 mois, ATCD AVC + diabète, IDM < 21j, chirurgie < 14j, UGD/VO.",
                "points": 3
            }
        ],
        "takeaway_points": [
            "ACA = hémiplégie crurale + syndrome frontal ; ACM = brachio-faciale.",
            "Fenêtre thrombolyse IV : < 4h30 ; maintenir PA < 185/110 mmHg.",
            "En cas de FA non valvulaire, anticoagulation curative différée après imagerie de contrôle (pas d'héparine en urgence à la phase aiguë sauf cas particuliers)."
        ]
    },
    {
        "slug": "neurochir_pott_compression_2025",
        "module_id": "neuro-neurochir",
        "sub_discipline": "Neurochirurgie",
        "course_hint": "spondylodiscite",
        "title": "Dorsalgies nocturnes, sueurs nocturnes et troubles de la marche (Cas Examen 2025 SN Copie 2)",
        "difficulty": "Élevée",
        "source_tag": "EXAMEN 2025 SN Neurochir Copie 2 + Pr Raouzi / Pr Khay",
        "patient_summary": "Patiente de 35 ans sans antécédent médico-chirurgical consulte pour des douleurs dorsales évoluant depuis 3 mois à recrudescence nocturne, associées à un amaigrissement et des sueurs nocturnes. Depuis 15 jours : lourdeur progressive des 2 membres inférieurs et douleurs en ceinture.",
        "vitals_json": {"PA": "115/70 mmHg", "FC": "88 bpm", "T°": "38,1 °C", "État général": "Amaigrissement 6 kg"},
        "steps_json": [
            {
                "step_number": 1,
                "step_type": "diagnosis",
                "prompt": "Quel est le syndrome neurologique urgent et l'étiologie la plus probable à évoquer en priorité ?",
                "clinical_reveal": "Examen neurologique : paraparésie spastique 3/5, réflexes ostéo-tendineux vifs et polycinétiques aux membres inférieurs, signe de Babinski bilatéral, niveau sensitif mamelonnaire (T4) et raideur rachidienne dorsale douloureuse à la percussion de D4-D5.",
                "question_format": "qcm_multi",
                "options": [
                    {"letter": "A", "text": "Compression médullaire lente dorsale (niveau T4) compliquant une spondylodiscite tuberculeuse (Mal de Pott)"},
                    {"letter": "B", "text": "Polyradiculonévrite aiguë de Guillain-Barré"},
                    {"letter": "C", "text": "Syndrome de la queue de cheval isolé"},
                    {"letter": "D", "text": "Sclérose latérale amyotrophique débutante"},
                    {"letter": "E", "text": "Canal lombaire étroit congénital"}
                ],
                "correct_answers": ["A"],
                "red_flags": ["Le Guillain-Barré donne une aréflexie périphérique sans niveau sensitif net ni douleur rachidienne fébrile."],
                "teaching_pearl": "Association caractéristique de l'Examen 2025 SN : syndrome rachidien (dorsalgies nocturnes fixes) + syndrome lésionnel (douleurs en ceinture) + syndrome sous-lésionnel pyramidal + contexte subaigu fébrile/sueurs au Maroc = Mal de Pott avec compression médullaire.",
                "points": 2
            },
            {
                "step_number": 2,
                "step_type": "workup_choice",
                "prompt": "Quel examen complémentaire demandez-vous en URGENCE absolue pour confirmer le mécanisme et guider le geste neurochirurgical ?",
                "clinical_reveal": "Bilan inflammatoire initial : CRP 68 mg/L, VS 72 mm/h, IDR positive à 16 mm.",
                "question_format": "qcm_multi",
                "options": [
                    {"letter": "A", "text": "IRM médullaire et rachidienne dorsale avec injection de gadolinium"},
                    {"letter": "B", "text": "Ponction lombaire d'emblée sous le niveau D4"},
                    {"letter": "C", "text": "Radiographie pulmonaire et bilan pré-thérapeutique antituberculeux (bilan hépatique, rénal)"},
                    {"letter": "D", "text": "Électromyogramme (ENMG) des 4 membres en urgence"},
                    {"letter": "E", "text": "Biopsie disco-vertébrale radioguidée / prélèvement per-opératoire pour preuve bactériologique & anapath"}
                ],
                "correct_answers": ["A", "C", "E"],
                "red_flags": ["La ponction lombaire est dangereuse en dessous d'une compression médullaire serrée (risque d'aggravation brutale par engagement médullaire)."],
                "teaching_pearl": "L'IRM rachidienne avec gadolinium est l'examen clé de toute compression médullaire : elle objective le pincement discal, le tassement en miroir D4-D5, l'abcès paravertébral / épidurite et le retentissement médullaire (hypersignal T2).",
                "points": 2
            },
            {
                "step_number": 3,
                "step_type": "management",
                "prompt": "L'IRM montre une spondylodiscite D4-D5 avec épidurite antérieure et compression médullaire sévère avec hypersignal T2. Quelle est la prise en charge immédiate ?",
                "clinical_reveal": "Aggravation rapide en 24h vers un déficit moteur côté à 2/5 avec troubles sphinctériens débutants.",
                "question_format": "qcm_multi",
                "options": [
                    {"letter": "A", "text": "Décompression médullaire chirurgicale urgente ± arthrodèse/stabilisation rachidienne + prélèvements"},
                    {"letter": "B", "text": "Traitement médical antituberculeux quadrithérapie (RHZE) pendant 9 à 12 mois + immobilisation"},
                    {"letter": "C", "text": "Kinésithérapie intensive immédiate de verticalisation sans traitement chirurgical"},
                    {"letter": "D", "text": "Surveillance simple par IRM à 3 mois"}
                ],
                "correct_answers": ["A", "B"],
                "red_flags": ["Ne jamais temporiser la décompression devant des signes déficitaires moteurs évolutifs ou sphinctériens."],
                "teaching_pearl": "Indication chirurgicale formelle dans le Mal de Pott : déficit neurologique évolutif / compression médullaire avec signes pyramido-sphinctériens, instabilité rachidienne majeure ou échec/doute diagnostique.",
                "points": 2
            }
        ],
        "takeaway_points": [
            "Triade sémiologique de la compression médullaire lente : syndrome rachidien + lésionnel + sous-lésionnel.",
            "IRM médullaire en urgence (jamais de PL avant imagerie devant un niveau sensitif).",
            "Mal de Pott compliqué de déficit neurologique = urgence médico-chirurgicale (décompression + quadrithérapie antituberculeuse)."
        ]
    },
    {
        "slug": "neuro_myasthenie_crise",
        "module_id": "neuro-neurochir",
        "sub_discipline": "Neurologie",
        "course_hint": "Myasthénie",
        "title": "Ptosis fluctuant, diplopie vespérale et fausse route récente",
        "difficulty": "Moyenne",
        "source_tag": "EXAMEN 2025 SN Neuro Q2-Q3 + Pr Yousfi",
        "patient_summary": "Femme de 29 ans consultant pour une chute de la paupière droite et une vision double prédominant en fin de journée depuis 2 mois. Depuis 3 jours après une infection ORL traitée par amoxicilline + gentamicine injectée, apparition d'une voix nasonnée et de difficultés à avaler les liquides.",
        "vitals_json": {"PA": "110/65 mmHg", "FC": "96 bpm", "FR": "24/min", "SpO2": "94%", "Capacité vitale": "En baisse"},
        "steps_json": [
            {
                "step_number": 1,
                "step_type": "workup_choice",
                "prompt": "Quels examens complémentaires confirment le diagnostic et recherchent une pathologie thymique associée ?",
                "clinical_reveal": "Manœuvre du glaçon positive sur le ptosis ; test de la fatigue positive aux bras tendus ; réflexes ostéo-tendineux normaux, pas de trouble sensitif.",
                "question_format": "qcm_multi",
                "options": [
                    {"letter": "A", "text": "ENMG avec stimulation répétitive montrant un décrément > 10 %"},
                    {"letter": "B", "text": "Dosage des anticorps anti-récepteurs à l'acétylcholine (anti-RACh) et anti-MuSK si négatifs"},
                    {"letter": "C", "text": "TDM thoracique à la recherche d'un thymome ou d'une hyperplasie thymique"},
                    {"letter": "D", "text": "Test pharmacologique à la prostigmine / néostigmine"},
                    {"letter": "E", "text": "Ponction lombaire montrant une dissociation albumino-cytologique"}
                ],
                "correct_answers": ["A", "B", "C", "D"],
                "red_flags": ["Oublier le scanner thoracique (bilan thymique systématique) expose à méconnaître un thymome."],
                "teaching_pearl": "Examen 2025 SN Neuro Q3 : les examens paracliniques clés de la myasthénie sont le test pharmacologique aux anticholinestérasiques, l'ENMG (décrément), les anticorps anti-RACh / anti-MuSK et la TDM thoracique.",
                "points": 2
            },
            {
                "step_number": 2,
                "step_type": "emergency_triage",
                "prompt": "Quelle est l'erreur thérapeutique ayant précipité l'aggravation bulbaire et quelle est la conduite d'urgence ?",
                "clinical_reveal": "Patient présente désormais dyspnée de décubitus, impossibilité de compter jusqu'à 15 d'un seul souffle, fausses routes sévères.",
                "question_format": "qcm_multi",
                "options": [
                    {"letter": "A", "text": "Arrêt immédiat de l'aminoside (gentamicine : médicament formellement contre-indiqué dans la myasthénie)"},
                    {"letter": "B", "text": "Hospitalisation en réanimation / soins intensifs pour surveillance respiratoire (CV, toux, encombrement)"},
                    {"letter": "C", "text": "Traitement de fond de la poussée sévère par Immunoglobulines IV (IgIV) ou échanges plasmatiques"},
                    {"letter": "D", "text": "Prescription de benzodiazépines pour calmer la dyspnée"}
                ],
                "correct_answers": ["A", "B", "C"],
                "red_flags": ["Les aminosides, bêta-bloquants, curares, macrolides, fluoroquinolones et benzodiazépines peuvent déclencher une crise myasthénique fatale !"],
                "teaching_pearl": "Signes bulbaires (dysphagie, dysphonie, troubles de la toux) + dyspnée = menace de crise myasthénique -> réanimation + arrêt des médicaments aggravants + IgIV ou échanges plasmatiques + adaptation des anticholinestérasiques.",
                "points": 2
            }
        ],
        "takeaway_points": [
            "Symptômes moteurs fluctuants aggravés à l'effort / vespéraux sans atteinte sensitive ni abolition des ROT = jonction neuromusculaire.",
            "Remettre systématiquement la liste des médicaments contre-indiqués au patient."
        ]
    },
    {
        "slug": "endo_hypothyroidie_grossesse_2025",
        "module_id": "endocrino-dermato",
        "sub_discipline": "Endocrinologie",
        "course_hint": "hypothyroidie",
        "title": "Hypothyroïdie fruste / patente découverte au 1er trimestre de grossesse (Vignette Examen 2025 SN)",
        "difficulty": "Moyenne",
        "source_tag": "EXAMEN 2025 SN Endocrino Vignette + Pr Latrech",
        "patient_summary": "Patiente de 28 ans enceinte à 9 SA consulte pour asthénie marquée et prise pondérale. Le bilan réalisé retrouve une TSH élevée à 6,2 mUI/L, FT4 limite basse, anticorps anti-TPO fortement positifs.",
        "vitals_json": {"PA": "105/65 mmHg", "FC": "62 bpm", "Terme": "9 SA", "BMI": "24 kg/m²"},
        "steps_json": [
            {
                "step_number": 1,
                "step_type": "interpretation",
                "prompt": "Comment interpréter la physiologie thyroïdienne au 1er trimestre et le profil biologique de cette patiente ?",
                "clinical_reveal": "Sous l'effet de l'hCG au 1er trimestre, la TSH physiologique de la femme enceinte tend normalement à diminuer (< 2,5 mUI/L).",
                "question_format": "qcm_multi",
                "options": [
                    {"letter": "A", "text": "Thyroïdite auto-immune d'Hashimoto (anti-TPO positifs) révélée ou aggravée par les besoins accrus de la grossesse"},
                    {"letter": "B", "text": "L'hCG a un effet TSH-like physiologique au 1er trimestre mais insuffisant ici face à la thyroïdite"},
                    {"letter": "C", "text": "L'hypothyroïdie maternelle non traitée expose à des risques de fausse couche, HTA gravidique et troubles neuro-développementaux fœtaux"},
                    {"letter": "D", "text": "Une TSH à 6,2 mUI/L avec anti-TPO positifs est tout à fait banale et ne nécessite aucun traitement durant la grossesse"}
                ],
                "correct_answers": ["A", "B", "C"],
                "red_flags": ["Attendre le 2e trimestre pour substituer alors que la thyroïde fœtale n'est fonctionnelle qu'à partir de 16-20 SA."],
                "teaching_pearl": "Le fœtus dépend entièrement des hormones thyroïdiennes maternelles (T4) durant la première moitié de la grossesse pour le développement cérébral.",
                "points": 2
            },
            {
                "step_number": 2,
                "step_type": "management",
                "prompt": "Quelle conduite thérapeutique adoptez-vous immédiatement et comment adapter le suivi ?",
                "clinical_reveal": "La patiente n'a pas de coronaropathie et souhaite mener la grossesse dans les meilleures conditions.",
                "question_format": "qcm_multi",
                "options": [
                    {"letter": "A", "text": "Débuter immédiatement la L-thyroxine (Lévothyrox) à pleine dose adaptée (sans attendre) pour viser une TSH < 2,5 mUI/L"},
                    {"letter": "B", "text": "Prendre la Lévothyroxine à jeun le matin à distance de la supplémentation en fer ou calcium (au moins 4h d'écart)"},
                    {"letter": "C", "text": "Contrôler la TSH toutes les 4 à 6 semaines pendant la grossesse et majorer les doses si besoin"},
                    {"letter": "D", "text": "Associer un antithyroïdien de synthèse (PTU) à la L-thyroxine"}
                ],
                "correct_answers": ["A", "B", "C"],
                "red_flags": ["Le fer et le calcium chélatent la L-thyroxine et réduisent son absorption digestive."],
                "teaching_pearl": "Chez la femme enceinte déjà hypothyroïdienne sous L-thyroxine, les doses doivent être augmentées de 25 à 50 % dès le début de la grossesse.",
                "points": 2
            }
        ],
        "takeaway_points": [
            "TSH cible au T1 < 2,5 mUI/L.",
            "Lévothyroxine à jeun, séparée du fer et du calcium."
        ]
    },
    {
        "slug": "endo_insuffisance_surrenalienne_aigue",
        "module_id": "endocrino-dermato",
        "sub_discipline": "Endocrinologie",
        "course_hint": "Insuffisance surrenalienne",
        "title": "Mélanodermie, douleurs abdominales aiguës et collapsus après gastro-entérite",
        "difficulty": "Élevée",
        "source_tag": "Cours Endocrino Pr Bouichrat + Résumé Mohamed IS",
        "patient_summary": "Jeune femme de 24 ans amenée aux urgences pour vomissements, douleurs abdominales diffuses et malaise lipothymique fébrile. Ses proches signalent un bronzage persistant des mains et des plis palmaires apparu depuis quelques mois malgré l'absence d'exposition solaire.",
        "vitals_json": {"PA": "75/45 mmHg", "FC": "124 bpm", "Glycémie": "0,52 g/L", "Na+": "126 mmol/L", "K+": "5,9 mmol/L"},
        "steps_json": [
            {
                "step_number": 1,
                "step_type": "diagnosis",
                "prompt": "Quel diagnostic d'urgence vitale posez-vous devant l'association hypotension + hyponatrémie + hyperkaliémie + hypoglycémie + mélanodermie ?",
                "clinical_reveal": "Biologie d'orientation urgente : natrémie 126 mmol/L, kaliémie 5,9 mmol/L, glycémie veineuse 0,50 g/L, hémoconcentration. Taches ardoisées sur la muqueuse buccale.",
                "question_format": "qcm_multi",
                "options": [
                    {"letter": "A", "text": "Insuffisance surrénalienne aiguë compliquant une maladie d'Addison (insuffisance surrénalienne lente périphérique)"},
                    {"letter": "B", "text": "Insuffisance antéhypophysaire aiguë pure"},
                    {"letter": "C", "text": "Acidocétose diabétique inaugurale"},
                    {"letter": "D", "text": "Phéochromocytome hémorragique"}
                ],
                "correct_answers": ["A"],
                "red_flags": ["L'insuffisance corticotrope (centrale) ne donne NI mélanodermie NI hyperkaliémie (l'aldostérone reste préservée)."],
                "teaching_pearl": "Mélanodermie + hyperkaliémie + hyponatrémie + hypoglycémie + collapsus = insuffisance surrénalienne primitive (périphérique) décompensée.",
                "points": 2
            },
            {
                "step_number": 2,
                "step_type": "management",
                "prompt": "Quelle est votre prise en charge immédiate en salle de déchoquage ?",
                "clinical_reveal": "Aucun résultat de cortisolémie n'est disponible avant 24h.",
                "question_format": "qcm_multi",
                "options": [
                    {"letter": "A", "text": "Ne JAMAIS attendre les résultats du dosage hormonal pour débuter le traitement (après un simple prélèvement de cortisol + ACTH si voie veineuse posée rapidement)"},
                    {"letter": "B", "text": "Hydrocortisone hémisuccinate 100 mg en bolus IVD puis 100-200 mg/24h à la seringue électrique"},
                    {"letter": "C", "text": "Remplissage vasculaire par NaCl 0,9 % + G5% / resucrage IV (SANS ajout de potassium !)"},
                    {"letter": "D", "text": "Traitement du facteur déclenchant (ici infectieux)"},
                    {"letter": "E", "text": "Furosémide IV pour corriger la surcharge"}
                ],
                "correct_answers": ["A", "B", "C", "D"],
                "red_flags": ["Attendre les dosages hormonaux ou ajouter du KCl dans la perfusion sont deux erreurs mortelles classiques !"],
                "teaching_pearl": "Traitement d'urgence de l'ISA : Hydrocortisone IV immédiate + réhydratation salée isotonique + glucose + traitement du facteur déclenchant.",
                "points": 3
            }
        ],
        "takeaway_points": [
            "Périphérique = ACTH haute (mélanodermie) + déficit aldostérone (hyperK+).",
            "Urgence absolue : traiter avant toute preuve biologique sur forte suspicion clinique."
        ]
    },
    {
        "slug": "endo_hypercalcemie_maligne",
        "module_id": "endocrino-dermato",
        "sub_discipline": "Endocrinologie",
        "course_hint": "Hypercalcémie",
        "title": "Confusion, polyurie-polydipsie et calcémie à 148 mg/L chez une patiente suivie pour cancer du sein",
        "difficulty": "Moyenne",
        "source_tag": "Cours Pr Rouf + Examen 2025 SN Q16-Q17",
        "patient_summary": "Patiente de 59 ans suivie pour adénocarcinome mammaire adressée pour syndrome polyuro-polydipsique, vomissements incoercibles, constipation et somnolence progressive. Calcémie corrigée mesurée à 148 mg/L (3,7 mmol/L).",
        "vitals_json": {"PA": "95/60 mmHg", "FC": "108 bpm", "ECG": "QT court, sus-décalage ST cupuliforme", "Creat": "19 mg/L"},
        "steps_json": [
            {
                "step_number": 1,
                "step_type": "interpretation",
                "prompt": "À l'ECG et au bilan biologique, quels signes confirment la gravité immédiate de cette hypercalcémie et orientent son mécanisme ?",
                "clinical_reveal": "PTH 1-84 très basse (< 8 pg/mL), phosphorémie basse, albuminémie à 30 g/L.",
                "question_format": "qcm_multi",
                "options": [
                    {"letter": "A", "text": "Raccourcissement de l'espace QT à l'ECG (et NON allongement !)"},
                    {"letter": "B", "text": "Hypercalcémie maligne sévère PTH-indépendante (ostéolyse métastatique ou sécrétion tumorale de PTHrp)"},
                    {"letter": "C", "text": "Déshydratation extracellulaire avec insuffisance rénale fonctionnelle aggravant l'hypercalcémie"},
                    {"letter": "D", "text": "Un adénome parathyroïdien est le diagnostic le plus probable compte tenu de la PTH basse"}
                ],
                "correct_answers": ["A", "B", "C"],
                "red_flags": ["Attention au piège d'examen 2025 SN Q16 : l'hypercalcémie RACCOURCIT le QT alors que l'hypocalcémie ALLONGE le QT."],
                "teaching_pearl": "Hypercalcémie + PTH effondrée = mécanisme PTH-indépendant (cancer avec métastases osseuses / PTHrp ou myélome/lymphome).",
                "points": 2
            },
            {
                "step_number": 2,
                "step_type": "management",
                "prompt": "Quelles mesures thérapeutiques urgentes mettez-vous en œuvre immédiatement ?",
                "clinical_reveal": "La patiente n'a pas d'OAP ni d'insuffisance cardiaque connue.",
                "question_format": "qcm_multi",
                "options": [
                    {"letter": "A", "text": "Réhydratation IV abondante par sérum salé isotonique (NaCl 0,9 %)"},
                    {"letter": "B", "text": "Bisphosphonate IV (acide zolédronique ou pamidronate) dont l'effet hypocalcémiant débute après 24-48h"},
                    {"letter": "C", "text": "Calcitonine SC/IV en urgence pour un effet rapide transitoire les 48 premières heures dans les formes menaçantes"},
                    {"letter": "D", "text": "Diurétiques thiazidiques d'emblée pour accélérer la calciurie"}
                ],
                "correct_answers": ["A", "B", "C"],
                "red_flags": ["Les diurétiques thiazidiques diminuent la calciurie et AGGRAVENT l'hypercalcémie ! Le furosémide ne s'utilise qu'après réhydratation correcte si surcharge."],
                "teaching_pearl": "Séquence vitale devant hypercalcémie maligne > 140 mg/L : Réhydratation NaCl 0,9% en 1er + Bisphosphonates IV + Calcitonine (relais précoce) + arrêt de tout apport vitamino-calcique / thiazidique / digitalique.",
                "points": 2
            }
        ],
        "takeaway_points": [
            "ECG : Hypercalcémie = QT court ; Hypocalcémie = QT long.",
            "Jamais de thiazidiques ni de digitaliques non surveillés lors d'une hypercalcémie."
        ]
    },
    {
        "slug": "dermato_pemphigus_vs_pb",
        "module_id": "endocrino-dermato",
        "sub_discipline": "Dermatologie",
        "course_hint": "Pemphigus",
        "title": "Érosions buccales rebelles suivies de bulles flasques du tronc avec signe de Nikolsky positif",
        "difficulty": "Moyenne",
        "source_tag": "QE ECN Dermato P1 + Cours Pr Zizi",
        "patient_summary": "Homme de 52 ans consulte pour des érosions buccales douloureuses évoluant depuis 2 mois rendant l'alimentation difficile, suivies depuis 3 semaines de bulles flasques sur peau saine se rompant rapidement en larges érosions suintantes sur le thorax et le cuir chevelu.",
        "vitals_json": {"PA": "120/75 mmHg", "Signe de Nikolsky": "Positif en peau péri-lésionnelle", "État cutané": "Bulles flasques sur peau non érythémateuse"},
        "steps_json": [
            {
                "step_number": 1,
                "step_type": "diagnosis",
                "prompt": "Quels éléments orientent vers un pemphigus vulgaire plutôt qu'une pemphigoïde bulleuse ?",
                "clinical_reveal": "Biopsie cutanée : clivage intra-épidermique suprabasal avec acantholyse. IFD : dépôts d'IgG et C3 en résille (en maille de filet) intercellulaire.",
                "question_format": "qcm_multi",
                "options": [
                    {"letter": "A", "text": "Atteinte muqueuse buccale inaugurale fréquente et sévère"},
                    {"letter": "B", "text": "Bulles flasques sur peau saine + signe de Nikolsky positif"},
                    {"letter": "C", "text": "Clivage intra-épidermique suprabasal et dépôts d'IgG/C3 intercellulaires en maille de filet à l'IFD"},
                    {"letter": "D", "text": "Bulles tendues prurigineuses sur plaques urticariennes chez le sujet âgé sans atteinte muqueuse"}
                ],
                "correct_answers": ["A", "B", "C"],
                "red_flags": ["L'item D décrit la pemphigoïde bulleuse (clivage sous-épidermique, IFD jonction dermo-épidermique linéaire)."],
                "teaching_pearl": "Pemphigus vulgaire : adulte d'âge moyen, début muqueux fréquent, bulles flasques, Nikolsky +, clivage intra-épidermique suprabasal, acantholyse, IFD en maille de filet, Ac anti-desmogléine 1 et 3.",
                "points": 2
            },
            {
                "step_number": 2,
                "step_type": "management",
                "prompt": "Quel est le traitement de première intention recommandé ?",
                "clinical_reveal": "Bilan pré-thérapeutique infectieux, glycémique et ostéodensitométrique effectué.",
                "question_format": "qcm_multi",
                "options": [
                    {"letter": "A", "text": "Corticothérapie générale systémique à forte dose (prednisone 1 à 1,5 mg/kg/j)"},
                    {"letter": "B", "text": "Association précoce au Rituximab (anti-CD20) permettant une épargne cortisonique et rémission prolongée"},
                    {"letter": "C", "text": "Soins locaux antiseptiques non traumatisants, bains de bouche, rééquilibration hydro-électrolytique et nutritionnelle"},
                    {"letter": "D", "text": "Dermocorticoïdes locaux seuls sans traitement systémique"}
                ],
                "correct_answers": ["A", "B", "C"],
                "red_flags": ["Les dermocorticoïdes seuls sont le traitement de la pemphigoïde bulleuse, insuffisants dans le pemphigus vulgaire où le pronostic vital est engagé."],
                "teaching_pearl": "Pemphigus vulgaire = urgence dermatologique grave : corticothérapie systémique ± Rituximab + soins locaux antiseptiques + prévention des complications infectieuses/cortisoniques.",
                "points": 2
            }
        ],
        "takeaway_points": [
            "Pemphigus = intra-épidermique (bulle flasque, Nikolsky +, muqueuses ++, maille de filet).",
            "Pemphigoïde = sous-épidermique (sujet âgé, bulle tendue, prurit, jonction dermo-épidermique linéaire)."
        ]
    },
    {
        "slug": "hemato_lam3_civd_urgence",
        "module_id": "hemato-onco",
        "sub_discipline": "Hématologie",
        "course_hint": "Leucémies aigues",
        "title": "Pancytopénie fébrile, gingivorragies et syndrome hémorragique sévère (LAM3 / CIVD)",
        "difficulty": "Élevée",
        "source_tag": "Cours Pr Alaoui + QE Pr Alaoui",
        "patient_summary": "Homme de 36 ans admis en urgence pour fièvre à 39°C, asthénie brutale, ecchymoses spontanées diffuses et épistaxis abondantes depuis 48h. NFS : Hb 6,8 g/dL, GB 3 200/mm³ avec cellules blastiques à corps d'Auer en fagots, Plaquettes 14 000/mm³.",
        "vitals_json": {"PA": "100/60 mmHg", "FC": "115 bpm", "TP": "42 %", "Fibrinogène": "0,7 g/L", "D-dimères": "Très élevés"},
        "steps_json": [
            {
                "step_number": 1,
                "step_type": "diagnosis",
                "prompt": "Quel sous-type de leucémie aiguë et quelle complication hémorragique aiguë identifiez-vous immédiatement ?",
                "clinical_reveal": "Myélogramme en urgence : 65 % de promyélocytes anormaux hypergranulaires avec nombreux bâtonnets d'Auer en fagots ; caryotype t(15;17) PML-RARA demandé.",
                "question_format": "qcm_multi",
                "options": [
                    {"letter": "A", "text": "Leucémie aiguë promyélocytaire (LAM3) associée à une translocation t(15;17)"},
                    {"letter": "B", "text": "Complication aiguë par Coagulation Intravasculaire Disséminée (CIVD) majeure"},
                    {"letter": "C", "text": "Le seuil diagnostique OMS de blastes médullaires pour poser le diagnostic de leucémie aiguë est ≥ 20 %"},
                    {"letter": "D", "text": "Une biopsie ostéo-médullaire est indispensable et prioritaire devant tout tableau de LAM"}
                ],
                "correct_answers": ["A", "B", "C"],
                "red_flags": ["Attention au piège QE Pr Alaoui : le seuil diagnostique est 20 % (pas 10 % ni 50 %), et c'est le myélogramme (pas la BOM) qui est l'examen clé."],
                "teaching_pearl": "LAM3 (promyélocytaire, t(15;17)) est une urgence hématologique absolue en raison du risque hémorragique cérébral/pulmonaire fatal par CIVD précoce.",
                "points": 2
            },
            {
                "step_number": 2,
                "step_type": "management",
                "prompt": "Quelles thérapeutiques instaurez-vous EN URGENCE avant même la confirmation cytogénétique définitive ?",
                "clinical_reveal": "Absence de signe neurologique focal ; bilan pré-transfusionnel prêt.",
                "question_format": "qcm_multi",
                "options": [
                    {"letter": "A", "text": "Introduction immédiate d'ATRA (acide tout-trans-rétinoïque / trétinoïne) qui corrige rapidement la CIVD"},
                    {"letter": "B", "text": "Support transfusionnel massif par Plasma Frais Congelé (PFC), concentrés plaquettaires et culots globulaires phénotypés"},
                    {"letter": "C", "text": "Antibiothérapie probabiliste à large spectre immédiate IV devant la neutropénie fébrile"},
                    {"letter": "D", "text": "Prévention du syndrome de lyse tumorale (hyperhydratation + allopurinol / rasburicase selon risque)"}
                ],
                "correct_answers": ["A", "B", "C", "D"],
                "red_flags": ["Oublier le PFC dans la CIVD ou différer l'ATRA expose au décès par hémorragie intracrânienne."],
                "teaching_pearl": "En cas de CIVD de LAM3 : ATRA urgent + transfusions plaquettaires (cible > 50 G/L) + PFC / fibrinogène + prise en charge de la neutropénie fébrile et du SLT.",
                "points": 3
            }
        ],
        "takeaway_points": [
            "LAM3 = corps d'Auer en fagots, t(15;17), CIVD sévère, urgence ATRA + PFC + plaquettes.",
            "Seuil diagnostique LA = ≥ 20 % blastes médullaires au myélogramme."
        ]
    },
    {
        "slug": "onco_syndrome_cave_superieur",
        "module_id": "hemato-onco",
        "sub_discipline": "Oncologie",
        "course_hint": "urgences Oncologiques",
        "title": "Œdème en pèlerine, turgescence jugulaire et dyspnée chez un fumeur (Urgence Oncologique)",
        "difficulty": "Moyenne",
        "source_tag": "Cours Urgences Onco 2026 Pr Mezouar + QE Onco",
        "patient_summary": "Homme de 58 ans, tabagique actif à 45 PA, consultant pour céphalées matinales, comblement des creux sus-claviculaires et bouffissure du visage s'aggravant en décubitus dorsal avec circulation veineuse collatérale thoracique.",
        "vitals_json": {"PA": "135/80 mmHg", "FC": "102 bpm", "SpO2": "91 % en air ambiant", "Position": "Orthopnée marquée"},
        "steps_json": [
            {
                "step_number": 1,
                "step_type": "workup_choice",
                "prompt": "Quel syndrome diagnostiquez-vous et quel examen d'imagerie réalisez-vous en première intention ?",
                "clinical_reveal": "Turgescence spontanée des veines jugulaires externes non pulsatile, œdème en pèlerine et cyanose de la face.",
                "question_format": "qcm_multi",
                "options": [
                    {"letter": "A", "text": "Syndrome cave supérieur (obstruction de la veine cave supérieure par compression extrinsèque, envahissement ou thrombose)"},
                    {"letter": "B", "text": "Scanner cervico-thoracique injecté en première intention"},
                    {"letter": "C", "text": "IRM cervico-thoracique obligatoire avant tout autre examen"},
                    {"letter": "D", "text": "Preuve histologique indispensable (bronchoscopie/biopsie) avant de choisir le traitement étiologique définitif hors détresse vitale"}
                ],
                "correct_answers": ["A", "B", "D"],
                "red_flags": ["Attention au piège QE Pr Mezouar : l'imagerie de 1er choix est le SCANNER cervico-thoracique (pas l'IRM) ; obstruction de la veine cave SUPÉRIEURE (pas inférieure) et hypertension veineuse EN AMONT (pas en aval)."],
                "teaching_pearl": "Le cancer bronchopulmonaire (notamment à petites cellules) et les lymphomes médiastinaux sont les premières étiologies du syndrome cave supérieur malin.",
                "points": 2
            },
            {
                "step_number": 2,
                "step_type": "management",
                "prompt": "En attendant le diagnostic histologique précis, quelles mesures thérapeutiques symptomatiques immédiates appliquez-vous ?",
                "clinical_reveal": "Le scanner montre une masse latéro-trachéale droite comprimant sévèrement la VCS sans thrombose étendue.",
                "question_format": "qcm_multi",
                "options": [
                    {"letter": "A", "text": "Position demi-assise (jamais décubitus strict)"},
                    {"letter": "B", "text": "Oxygénothérapie adaptée à la SpO2"},
                    {"letter": "C", "text": "Corticothérapie systémique pour réduire l'œdème péri-tumoral (après ou en coordination avec la biopsie si suspicion de lymphome, sauf urgence vitale)"},
                    {"letter": "D", "text": "Pose d'endoprothèse (stent) cave supérieure à discuter rapidement si menace asphyxique ou syndrome sévère réfractaire"}
                ],
                "correct_answers": ["A", "B", "C", "D"],
                "red_flags": ["Poser les voies veineuses périphériques aux membres inférieurs si possible plutôt qu'au membre supérieur comprimé."],
                "teaching_pearl": "Position demi-assise + O2 ne sont JAMAIS suffisants seuls : ils accompagnent le traitement étiologique (chimiothérapie/radiothérapie selon histologie) ± stent cave si urgence extrême.",
                "points": 2
            }
        ],
        "takeaway_points": [
            "Syndrome cave supérieur = scanner cervico-thoracique injecté.",
            "Mesures immédiates : position demi-assise + O2 + recherche de signes de gravité laryngés/cérébraux."
        ]
    },
    {
        "slug": "anapath_vessie_cis_vs_papillaire",
        "module_id": "anapath",
        "sub_discipline": "Anatomopathologie",
        "course_hint": "vessie",
        "title": "Hématurie macroscopique chez un fumeur : lecture anatomopathologique d'une résection trans-urétrale de vessie",
        "difficulty": "Moyenne",
        "source_tag": "QE PR KARICH + Examen 2025 SN APS",
        "patient_summary": "Homme de 67 ans, ancien ouvrier de l'industrie textile et fumeur 50 PA, exploré pour hématurie macroscopique totale indolore. L'urologue réalise une cystoscopie et vous adresse des copeaux de RTUV issus de deux zones distinctes.",
        "vitals_json": {"Zone A (dôme)": "Plage plane rougeâtre veloutée", "Zone B (paroi latérale)": "Formation bourgeonnante frangée"},
        "steps_json": [
            {
                "step_number": 1,
                "step_type": "interpretation",
                "prompt": "Zone A (lésion plane rougeâtre) : l'histologie montre une désorganisation architecturale majeure, des atypies cytonucléaires marquées sur toute la hauteur de l'urothélium, sans franchissement de la membrane basale. Quel diagnostic anapath retenez-vous ?",
                "clinical_reveal": "Copeaux A : épithélium plat remanié mais chorion indemne d'invasion.",
                "question_format": "qcm_multi",
                "options": [
                    {"letter": "A", "text": "Carcinome urothélial in situ (CIS)"},
                    {"letter": "B", "text": "Papillome urothélial"},
                    {"letter": "C", "text": "Néoplasie papillaire de faible potentiel de malignité (LMP)"},
                    {"letter": "D", "text": "Carcinome urothélial papillaire de bas grade pTa"}
                ],
                "correct_answers": ["A"],
                "red_flags": ["Confondre un CIS plan de haut grade à fort potentiel d'invasion avec un papillome bénin."],
                "teaching_pearl": "Classique absolu de Pr Karich et Examen 2025 SN APS : Lésion PLANE rougeâtre + désorganisation architecturale majeure + atypies marquées sans invasion du chorion = Carcinome urothélial In Situ (CIS).",
                "points": 2
            },
            {
                "step_number": 2,
                "step_type": "interpretation",
                "prompt": "Zone B : tumeur végétante d'architecture papillaire montrant une polarité conservée, une épaisseur épithéliale > 7 couches, des mitoses rares basales et des atypies minimes, n'infiltrant pas le muscle détrusor ni le chorion. De quoi s'agit-il ?",
                "clinical_reveal": "La couche musculaire détrusorienne est représentée sur les copeaux et indemne de tumeur.",
                "question_format": "qcm_multi",
                "options": [
                    {"letter": "A", "text": "Tumeur de vessie n'infiltrant pas le muscle (TVNIM) pTa"},
                    {"letter": "B", "text": "Néoplasie papillaire de faible potentiel de malignité / bas grade selon densité atypique"},
                    {"letter": "C", "text": "Présence obligatoire du détrusor sur les copeaux pour affirmer l'absence d'infiltration musculaire (pT2)"},
                    {"letter": "D", "text": "Tumeur infiltrant le muscle (pT2)"}
                ],
                "correct_answers": ["A", "B", "C"],
                "red_flags": ["En l'absence de musculeuse visible sur le prélèvement de RTUV, une re-résection (second look) est souvent nécessaire."],
                "teaching_pearl": "Le papillome urothélial vrai ne dépasse PAS 6 couches cellulaires et n'a aucune atypie ni mitose en surface ; la classification distingue TVNIM (pTis, pTa, pT1) et TVIM (≥ pT2).",
                "points": 2
            }
        ],
        "takeaway_points": [
            "Lésion plane + atypies majeures = CIS.",
            "Papillome = franges grêles, ≤ 6 couches d'urothélium normal, pas d'atypies."
        ]
    },
    {
        "slug": "anapath_thyroide_bethesda_papillaire",
        "module_id": "anapath",
        "sub_discipline": "Anatomopathologie",
        "course_hint": "cancer de la thyroide",
        "title": "Nodule thyroïdien suspect : de la cytoponction Bethesda à l'anatomopathologie opératoire",
        "difficulty": "Moyenne",
        "source_tag": "Cours Pr Halaoui + Examen 2025 SN Endo Q18",
        "patient_summary": "Patiente de 32 ans ayant reçu une irradiation cervicale dans l'enfance présente un nodule thyroïdien droit EU-TIRADS 5 de 2,4 cm avec adénopathie jugulo-carotidienne homolatérale.",
        "vitals_json": {"TSH": "1,8 mUI/L (normale)", "Calcitonine": "Normale", "Cytoponction": "Bethesda VI"},
        "steps_json": [
            {
                "step_number": 1,
                "step_type": "interpretation",
                "prompt": "À propos de la cytoponction thyroïdienne et des critères anatomopathologiques attendus, quelles affirmations sont exactes ?",
                "clinical_reveal": "Pièce de thyroïdectomie totale + curage adressée à l'anapath : noyaux clairs en verre dépoli (Orphan Annie), incisures nucléaires (« grains de café »), pseudo-inclusions intranucléaires et calcifications en psammomes.",
                "question_format": "qcm_multi",
                "options": [
                    {"letter": "A", "text": "La classification cytologique de Bethesda comporte 6 catégories (du I non satisfaisant au VI malin)"},
                    {"letter": "B", "text": "Ces aspects nucléaires (noyaux clairs en verre dépoli, incisures, pseudo-inclusions, psammomes) signent un carcinome papillaire de la thyroïde"},
                    {"letter": "C", "text": "L'antécédent d'irradiation cervicale dans l'enfance est un facteur de risque classique du cancer papillaire"},
                    {"letter": "D", "text": "L'extension lymphatique ganglionnaire est typique du carcinome papillaire alors que le folliculaire/vésiculaire dissémine surtout par voie hématogène"}
                ],
                "correct_answers": ["A", "B", "C", "D"],
                "red_flags": ["Ne jamais confondre : carcinome médullaire -> cellules C + substance amyloïde + calcitonine élevée + NEM2."],
                "teaching_pearl": "Doublé gagnant S7 (Endocrino Pr Rouf + Anapath Pr Halaoui) : Bethesda = 6 catégories ; Papillaire = critères nucléaires + extension ganglionnaire.",
                "points": 3
            }
        ],
        "takeaway_points": [
            "Bethesda = 6 catégories cytologiques (≠ TIRADS échographique en 5 grades).",
            "Carcinome papillaire = diagnostic avant tout NUCLÉAIRE."
        ]
    }
]


def main() -> None:
    init_db(DB_PATH)
    conn = get_conn(DB_PATH)
    course_rows = conn.execute("SELECT id, module_id, canonical_title, professor FROM courses").fetchall()

    inserted = 0
    for c in CASES:
        best_cid = None
        best_sc = 0.0
        for cr in course_rows:
            if cr["module_id"] != c["module_id"]:
                continue
            sc = token_score(cr["canonical_title"], c["course_hint"], cr["professor"], None)
            if sc > best_sc:
                best_sc = sc
                best_cid = cr["id"]

        takeaways = c["takeaway_points"]
        conn.execute(
            """
            INSERT INTO clinical_cases (
                slug, module_id, sub_discipline, course_id, title, difficulty,
                source_tag, patient_summary, vitals_json, steps_json, takeaway_points
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
                title=excluded.title,
                patient_summary=excluded.patient_summary,
                vitals_json=excluded.vitals_json,
                steps_json=excluded.steps_json,
                takeaway_points=excluded.takeaway_points,
                course_id=excluded.course_id
            """,
            (
                c["slug"], c["module_id"], c["sub_discipline"], best_cid,
                c["title"], c["difficulty"], c["source_tag"],
                c["patient_summary"],
                json.dumps(c["vitals_json"], ensure_ascii=False),
                json.dumps(c["steps_json"], ensure_ascii=False),
                json.dumps(takeaways, ensure_ascii=False),
            ),
        )
        inserted += 1

    conn.commit()
    conn.close()
    print(f"Seeded {inserted} multi-step interactive clinical cases.")


if __name__ == "__main__":
    main()
