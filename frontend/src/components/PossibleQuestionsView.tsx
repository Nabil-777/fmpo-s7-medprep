import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  FileText,
  Flame,
  RotateCcw,
  Search,
  Sparkles,
  Stethoscope,
  XCircle,
} from 'lucide-react';
import { api } from '../api';
import type {
  AttemptResult,
  ClinicalCaseItem,
  NavTab,
  PossibleQuestionsResponse,
  QuestionItem,
} from '../types';
import { ClinicalCasePlayer } from './ClinicalCasePlayer';
import { MODULE_ROMAN, ModuleBadge, sortModulesEditorial } from './shared';

interface Props {
  initialPreset?: {
    module_id?: string;
    course_id?: number;
    tab?: 'questions' | 'cases';
    slug?: string;
  } | null;
  onNavigate: (tab: NavTab, preset?: any) => void;
}

const QUESTION_TYPE_LABELS: Record<string, string> = {
  qcm_multi: 'QCM Multi',
  qcm_group: 'QCM Group A–E',
  qroc: 'QROC Rédigée',
  synthesis: 'Synthèse',
};

export const PossibleQuestionsView: React.FC<Props> = ({ initialPreset, onNavigate }) => {
  const [subTab, setSubTab] = useState<'questions' | 'cases'>(initialPreset?.tab || 'questions');
  const [moduleFilter, setModuleFilter] = useState<string>(initialPreset?.module_id || 'all');
  const [courseFilter, setCourseFilter] = useState<string>(
    initialPreset?.course_id ? String(initialPreset.course_id) : '',
  );
  const [difficultyFilter, setDifficultyFilter] = useState<string>('all');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [zeroAnnaleOnly, setZeroAnnaleOnly] = useState<boolean>(false);
  const [searchText, setSearchText] = useState<string>('');

  const [data, setData] = useState<PossibleQuestionsResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [activeQIdx, setActiveQIdx] = useState<number>(0);

  const [selectedMap, setSelectedMap] = useState<Record<number, string[]>>({});
  const [writtenMap, setWrittenMap] = useState<Record<number, string>>({});
  const [resultsMap, setResultsMap] = useState<Record<number, AttemptResult>>({});
  const [submittingId, setSubmittingId] = useState<number | null>(null);

  const [activeCase, setActiveCase] = useState<ClinicalCaseItem | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res: PossibleQuestionsResponse = await api.possibleQuestions({
        module_id: moduleFilter,
        course_id: courseFilter,
        difficulty_tier: difficultyFilter,
        question_type: typeFilter,
        zero_annale_only: zeroAnnaleOnly ? 'true' : '',
        q: searchText.trim(),
        limit: 400,
      });
      setData(res);
      setActiveQIdx((prev) => (res.questions.length === 0 ? 0 : Math.min(prev, res.questions.length - 1)));
      if (initialPreset?.slug && !activeCase) {
        const match = res.cases.find((c) => c.slug === initialPreset.slug);
        if (match) setActiveCase(match);
      }
    } finally {
      setLoading(false);
    }
  }, [moduleFilter, courseFilter, difficultyFilter, typeFilter, zeroAnnaleOnly, searchText]);

  useEffect(() => {
    const t = setTimeout(() => {
      fetchData();
    }, searchText ? 220 : 0);
    return () => clearTimeout(t);
  }, [fetchData, searchText]);

  const orderedModules = useMemo(() => {
    const raw = (data?.by_module || []).map((m) => ({ ...m, id: m.module_id }));
    return sortModulesEditorial(raw);
  }, [data?.by_module]);

  const visibleCourses = useMemo(() => {
    const all = data?.courses || [];
    if (moduleFilter === 'all') return all;
    return all.filter((c) => c.module_id === moduleFilter);
  }, [data?.courses, moduleFilter]);

  const questions = data?.questions || [];
  const cases = data?.cases || [];
  const currentQ: QuestionItem | undefined = questions[activeQIdx];

  const toggleOption = (q: QuestionItem, letter: string) => {
    if (resultsMap[q.id]) return;
    const isSingle = q.question_type === 'qcm_group';
    const cur = selectedMap[q.id] || [];
    if (isSingle) {
      setSelectedMap({ ...selectedMap, [q.id]: [letter] });
      return;
    }
    const next = cur.includes(letter) ? cur.filter((x) => x !== letter) : [...cur, letter];
    setSelectedMap({ ...selectedMap, [q.id]: next.sort() });
  };

  const handleSubmit = async (q: QuestionItem) => {
    setSubmittingId(q.id);
    try {
      const isWritten = q.question_type === 'qroc' || q.question_type === 'synthesis';
      const res = await api.attemptQuestion(q.id, {
        session_id: 'possible_question',
        mode: q.question_type || 'practice',
        selected_answers: isWritten ? [] : selectedMap[q.id] || [],
        written_answer: isWritten ? writtenMap[q.id] || '' : '',
      });
      setResultsMap((prev) => ({ ...prev, [q.id]: res }));
    } finally {
      setSubmittingId(null);
    }
  };

  const handleRetryQuestion = (qid: number) => {
    setResultsMap((prev) => {
      const copy = { ...prev };
      delete copy[qid];
      return copy;
    });
    setSelectedMap((prev) => {
      const copy = { ...prev };
      delete copy[qid];
      return copy;
    });
    setWrittenMap((prev) => {
      const copy = { ...prev };
      delete copy[qid];
      return copy;
    });
  };

  if (subTab === 'cases' && activeCase) {
    return (
      <ClinicalCasePlayer
        key={activeCase.id}
        activeCase={activeCase}
        backLabel="Tous les cas cliniques complexes"
        onBack={() => setActiveCase(null)}
        onAttemptRecorded={fetchData}
        onNavigate={onNavigate}
      />
    );
  }

  const summary = data?.summary;
  const currentResult = currentQ ? resultsMap[currentQ.id] : undefined;
  const isCurrentWritten =
    currentQ?.question_type === 'qroc' || currentQ?.question_type === 'synthesis';
  const currentSelected = currentQ ? selectedMap[currentQ.id] || [] : [];
  const canSubmit = Boolean(
    currentQ &&
      !currentResult &&
      (isCurrentWritten ? (writtenMap[currentQ.id] || '').trim().length > 1 : currentSelected.length > 0),
  );

  return (
    <div className="space-y-6">
      {/* Top Broadsheet Header + 4 Tabular Metrics */}
      <section className="bg-white border border-[#E5DFD3] rounded-[5px] p-6 space-y-5">
        <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
          <div className="space-y-2 max-w-3xl">
            <div className="inline-flex items-center gap-2 text-[9.5px] font-bold tracking-[0.16em] uppercase text-[#9A7438]">
              <Sparkles className="w-3.5 h-3.5" />
              BANQUE PRÉDICTIVE S7 · EXTRACTION INTÉGRALE DES SUPPORTS DE COURS
            </div>
            <h1 className="font-serif-editorial text-[28px] sm:text-[34px] leading-[1.15] text-[#161615] font-normal">
              Possible Question <span className="italic text-[#6B1D2F]">· Pièges & Cas Complexes</span>
            </h1>
            <p className="text-[13px] text-[#6F6A61] leading-relaxed">
              Questions sélectives (« wa3rin / pièges jury ») et situations cliniques complexes en 4 temps
              générées directement à partir des {summary?.docs_analyzed ?? '—'} cours et résumés S7, en
              ciblant les seuils critiques et les chapitres encore absents des annales.
            </p>
          </div>

          {/* Mode Switcher */}
          <div className="inline-flex rounded-[4px] bg-[#F3EFE7] border border-[#D2C9B8] p-1 shrink-0">
            <button
              onClick={() => {
                setSubTab('questions');
                setActiveCase(null);
              }}
              className={`px-4 py-2 rounded-[3px] text-xs font-semibold transition cursor-pointer flex items-center gap-2 ${
                subTab === 'questions'
                  ? 'bg-[#6B1D2F] text-white'
                  : 'text-[#6F6A61] hover:text-[#161615]'
              }`}
            >
              <Flame className="w-3.5 h-3.5" />
              <span>Questions Wa3rin ({summary?.total_questions ?? 0})</span>
            </button>
            <button
              onClick={() => setSubTab('cases')}
              className={`px-4 py-2 rounded-[3px] text-xs font-semibold transition cursor-pointer flex items-center gap-2 ${
                subTab === 'cases'
                  ? 'bg-[#6B1D2F] text-white'
                  : 'text-[#6F6A61] hover:text-[#161615]'
              }`}
            >
              <Stethoscope className="w-3.5 h-3.5" />
              <span>Cas Cliniques Complexes ({summary?.total_cases ?? 0})</span>
            </button>
          </div>
        </div>

        {/* 4 Editorial KPI Strip */}
        <div className="grid grid-cols-2 lg:grid-cols-4 border border-[#E5DFD3] rounded-[4px] bg-[#FBF9F5] divide-y lg:divide-y-0 lg:divide-x divide-[#E5DFD3]">
          <div className="px-4 py-3">
            <div className="text-[9px] font-bold tracking-[0.14em] uppercase text-[#6F6A61]">
              QUESTIONS PRÉDITES
            </div>
            <div className="font-serif-editorial text-[24px] tabular-nums text-[#161615] mt-0.5">
              {summary?.total_questions ?? '—'}
            </div>
            <div className="text-[11px] text-[#6F6A61]">
              sur {summary?.doc_backed_courses ?? '—'} chapitres documentés
            </div>
          </div>

          <div className="px-4 py-3">
            <div className="text-[9px] font-bold tracking-[0.14em] uppercase text-[#9E2A2B]">
              PIÈGES JURY
            </div>
            <div className="font-serif-editorial text-[24px] tabular-nums text-[#9E2A2B] mt-0.5">
              {summary?.piege_jury_count ?? '—'}
            </div>
            <div className="text-[11px] text-[#6F6A61]">seuils, négations & diagnostics fins</div>
          </div>

          <div className="px-4 py-3">
            <div className="text-[9px] font-bold tracking-[0.14em] uppercase text-[#9A7438]">
              HORS-ANNALES (0 ANNALE)
            </div>
            <div className="font-serif-editorial text-[24px] tabular-nums text-[#9A7438] mt-0.5">
              {summary?.zero_annale_questions ?? '—'}
            </div>
            <div className="text-[11px] text-[#6F6A61]">sujets vierges à haut risque de tombée</div>
          </div>

          <div className="px-4 py-3">
            <div className="text-[9px] font-bold tracking-[0.14em] uppercase text-[#2A5C48]">
              DOSSIERS CLINIQUES
            </div>
            <div className="font-serif-editorial text-[24px] tabular-nums text-[#2A5C48] mt-0.5">
              {summary?.total_cases ?? '—'}
            </div>
            <div className="text-[11px] text-[#6F6A61]">situations progressives en 4 étapes</div>
          </div>
        </div>

        {/* Module Pills + Filter Toolbar */}
        <div className="space-y-3 pt-1 border-t border-[#E5DFD3]">
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => {
                setModuleFilter('all');
                setCourseFilter('');
                setActiveQIdx(0);
              }}
              className={`px-3 py-1.5 rounded-[4px] text-xs font-semibold border transition cursor-pointer ${
                moduleFilter === 'all'
                  ? 'bg-[#241116] border-[#241116] text-[#FBF9F5]'
                  : 'bg-[#FBF9F5] border-[#D2C9B8] text-[#161615] hover:border-[#9A7438]'
              }`}
            >
              Tous les modules
            </button>
            {orderedModules.map((m) => {
              const active = moduleFilter === m.module_id;
              const cnt = subTab === 'questions' ? m.q_count : m.case_count;
              return (
                <button
                  key={m.module_id}
                  onClick={() => {
                    setModuleFilter(m.module_id);
                    setCourseFilter('');
                    setActiveQIdx(0);
                  }}
                  className={`px-3 py-1.5 rounded-[4px] text-xs font-semibold border transition cursor-pointer inline-flex items-center gap-1.5 ${
                    active
                      ? 'bg-[#6B1D2F] border-[#6B1D2F] text-white'
                      : 'bg-white border-[#D2C9B8] text-[#161615] hover:border-[#9A7438]'
                  }`}
                >
                  <span className="opacity-75">{MODULE_ROMAN[m.module_id]}</span>
                  <span>{m.short_name || m.name}</span>
                  <span
                    className={`font-mono-tabular text-[10.5px] px-1.5 py-0.2 rounded-[3px] ${
                      active ? 'bg-white/20 text-white' : 'bg-[#F3EFE7] text-[#6F6A61]'
                    }`}
                  >
                    {cnt}
                  </span>
                </button>
              );
            })}
          </div>

          {subTab === 'questions' && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-12 gap-2.5 items-center">
              <div className="lg:col-span-4 relative">
                <Search className="w-3.5 h-3.5 text-[#6F6A61] absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={searchText}
                  onChange={(e) => {
                    setSearchText(e.target.value);
                    setActiveQIdx(0);
                  }}
                  placeholder="Rechercher un piège, score, anticorps, seuil…"
                  className="w-full pl-8 pr-3 py-2 text-xs rounded-[4px] border border-[#D2C9B8] bg-[#FBF9F5] focus:bg-white focus:border-[#6B1D2F] focus:outline-none text-[#161615]"
                />
              </div>

              <select
                value={courseFilter}
                onChange={(e) => {
                  setCourseFilter(e.target.value);
                  setActiveQIdx(0);
                }}
                className="lg:col-span-3 px-3 py-2 text-xs font-medium rounded-[4px] border border-[#D2C9B8] bg-[#FBF9F5] text-[#161615]"
              >
                <option value="">Tous les chapitres ({visibleCourses.length})</option>
                {visibleCourses.map((c) => (
                  <option key={c.id} value={String(c.id)}>
                    {c.annale_cnt === 0 ? '[0 annale] ' : `[${c.annale_cnt} ann.] `}
                    {c.canonical_title} ({c.predicted_cnt})
                  </option>
                ))}
              </select>

              <select
                value={difficultyFilter}
                onChange={(e) => {
                  setDifficultyFilter(e.target.value);
                  setActiveQIdx(0);
                }}
                className="lg:col-span-2 px-3 py-2 text-xs font-medium rounded-[4px] border border-[#D2C9B8] bg-[#FBF9F5] text-[#161615]"
              >
                <option value="all">Toute difficulté</option>
                <option value="piege_jury">Piège Jury uniquement</option>
                <option value="wa3ra">Wa3ra sélective</option>
              </select>

              <select
                value={typeFilter}
                onChange={(e) => {
                  setTypeFilter(e.target.value);
                  setActiveQIdx(0);
                }}
                className="lg:col-span-2 px-3 py-2 text-xs font-medium rounded-[4px] border border-[#D2C9B8] bg-[#FBF9F5] text-[#161615]"
              >
                <option value="all">Tous formats</option>
                <option value="qcm_multi">QCM Multi</option>
                <option value="qcm_group">QCM Group A–E</option>
                <option value="qroc">QROC Rédigée</option>
              </select>

              <label className="lg:col-span-1 flex items-center gap-1.5 text-[11px] font-semibold text-[#9A7438] cursor-pointer whitespace-nowrap justify-end">
                <input
                  type="checkbox"
                  checked={zeroAnnaleOnly}
                  onChange={(e) => {
                    setZeroAnnaleOnly(e.target.checked);
                    setActiveQIdx(0);
                  }}
                  className="accent-[#6B1D2F]"
                />
                <span>0 annale</span>
              </label>
            </div>
          )}
        </div>
      </section>

      {/* Main Workspace */}
      {subTab === 'questions' ? (
        loading && questions.length === 0 ? (
          <div className="bg-white border border-[#E5DFD3] rounded-[5px] p-12 text-center font-serif-editorial italic text-lg text-[#6F6A61]">
            Chargement de la banque prédictive…
          </div>
        ) : questions.length === 0 ? (
          <div className="bg-white border border-[#E5DFD3] rounded-[5px] p-10 text-center space-y-2">
            <p className="font-serif-editorial text-xl text-[#161615]">
              Aucune question ne correspond à ces filtres.
            </p>
            <p className="text-xs text-[#6F6A61]">
              Élargissez la recherche ou réinitialisez le filtre chapitre / format.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
            {/* Left 4 Cols: Question Focus Folio Index */}
            <aside className="lg:col-span-4 bg-white border border-[#E5DFD3] rounded-[5px] overflow-hidden">
              <div className="px-4 py-3 bg-[#F3EFE7] border-b border-[#D2C9B8] flex items-center justify-between">
                <span className="text-[9.5px] font-bold tracking-[0.14em] uppercase text-[#6F6A61]">
                  INDEX DES QUESTIONS ({questions.length})
                </span>
                <span className="font-mono-tabular text-[10.5px] font-bold text-[#6B1D2F]">
                  {Object.keys(resultsMap).length} traitée(s)
                </span>
              </div>

              <div className="max-h-[680px] overflow-y-auto divide-y divide-[#E5DFD3]">
                {questions.map((q, i) => {
                  const isActive = i === activeQIdx;
                  const r = resultsMap[q.id];
                  const isPiege = q.difficulty_tier === 'piege_jury';
                  return (
                    <button
                      key={q.id}
                      onClick={() => setActiveQIdx(i)}
                      className={`w-full text-left px-4 py-3 transition cursor-pointer border-l-3 ${
                        isActive
                          ? 'bg-[#FBF5EE] border-l-[#6B1D2F]'
                          : 'bg-white border-l-transparent hover:bg-[#FBF9F5]'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className="font-mono-tabular text-[10.5px] font-bold text-[#6F6A61]">
                            #{String(i + 1).padStart(2, '0')}
                          </span>
                          <span
                            className={`px-1.5 py-0.5 rounded-[3px] text-[9px] font-bold uppercase tracking-wider ${
                              isPiege
                                ? 'bg-[#FAF0F0] text-[#9E2A2B] border border-[#E5B8B8]'
                                : 'bg-[#FBF5EE] text-[#9A7438] border border-[#DFC9A6]'
                            }`}
                          >
                            {isPiege ? 'Piège Jury' : 'Wa3ra'}
                          </span>
                          {q.course_annale_cnt === 0 && (
                            <span className="px-1.5 py-0.5 rounded-[3px] text-[9px] font-bold bg-[#241116] text-[#FBF9F5]">
                              0 annale
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-1.5 shrink-0">
                          {r ? (
                            r.is_correct ? (
                              <CheckCircle2 className="w-3.5 h-3.5 text-[#2A5C48]" />
                            ) : (
                              <XCircle className="w-3.5 h-3.5 text-[#9E2A2B]" />
                            )
                          ) : null}
                          <span className="font-mono-tabular text-[10px] font-semibold text-[#9A7438]">
                            {q.likelihood_score ?? 80}%
                          </span>
                        </div>
                      </div>

                      <div className="text-[12px] font-semibold text-[#161615] line-clamp-1">
                        {q.course_title || q.sub_discipline}
                      </div>
                      <div className="text-[11.5px] text-[#6F6A61] line-clamp-2 mt-0.5 leading-snug">
                        {q.stem}
                      </div>
                    </button>
                  );
                })}
              </div>
            </aside>

            {/* Right 8 Cols: Active Examination & Debrief Desk */}
            {currentQ && (
              <div className="lg:col-span-8 bg-white border border-[#E5DFD3] rounded-[5px] p-6 md:p-7 space-y-5">
                {/* Meta Ribbon */}
                <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-[#E5DFD3]">
                  <div className="flex flex-wrap items-center gap-2">
                    <ModuleBadge moduleId={currentQ.module_id} sub={currentQ.sub_discipline} />
                    <span
                      className={`px-2.5 py-0.5 rounded-[4px] text-[10.5px] font-bold uppercase tracking-wider ${
                        currentQ.difficulty_tier === 'piege_jury'
                          ? 'bg-[#FAF0F0] text-[#9E2A2B] border border-[#E5B8B8]'
                          : 'bg-[#FBF5EE] text-[#9A7438] border border-[#DFC9A6]'
                      }`}
                    >
                      {currentQ.difficulty_tier === 'piege_jury' ? 'Piège Jury' : 'Wa3ra'}
                    </span>
                    <span className="px-2 py-0.5 rounded-[4px] text-[10.5px] font-semibold bg-[#F3EFE7] text-[#161615] border border-[#D2C9B8]">
                      {QUESTION_TYPE_LABELS[currentQ.question_type] || currentQ.question_type}
                    </span>
                    {currentQ.course_annale_cnt === 0 && (
                      <span className="px-2 py-0.5 rounded-[4px] text-[10.5px] font-semibold bg-[#241116] text-[#FBF9F5]">
                        Hors-annales (0 Q annale)
                      </span>
                    )}
                  </div>

                  <div className="font-mono-tabular text-[11px] font-bold text-[#9A7438]">
                    Probabilité tombée : {currentQ.likelihood_score ?? 80}%
                  </div>
                </div>

                {/* Stem & Chapter */}
                <div>
                  <h2 className="font-serif-editorial text-[23px] sm:text-[25px] leading-snug font-normal text-[#161615]">
                    {currentQ.stem}
                  </h2>
                  {currentQ.course_title && (
                    <p className="text-[11.5px] text-[#6F6A61] mt-1.5">
                      Chapitre source : <strong className="text-[#161615]">{currentQ.course_title}</strong>
                      {currentQ.professor ? ` · ${currentQ.professor}` : ''}
                    </p>
                  )}
                </div>

                {currentQ.vignette_text && (
                  <div className="p-4 rounded-[4px] bg-[#F3EFE7] border border-[#D2C9B8] text-[13px] text-[#161615] leading-relaxed">
                    <div className="text-[9px] font-bold tracking-[0.12em] uppercase text-[#9A7438] mb-1">
                      VIGNETTE CLINIQUE
                    </div>
                    {currentQ.vignette_text}
                  </div>
                )}

                {currentQ.statements_json && currentQ.statements_json.length > 0 && (
                  <div className="rounded-[4px] bg-[#FBF9F5] border border-[#D2C9B8] p-4 space-y-2">
                    <div className="text-[9px] font-bold tracking-[0.12em] uppercase text-[#6F6A61]">
                      PROPOSITIONS (CHOIX UNIQUE REGROUPÉ A–E)
                    </div>
                    {currentQ.statements_json.map((st) => (
                      <div key={st.letter} className="text-[12.5px] text-[#161615] flex gap-2.5">
                        <span className="font-semibold text-[#6F6A61] w-5 shrink-0">{st.letter})</span>
                        <span>{st.text}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Answer Input */}
                {isCurrentWritten ? (
                  <div className="space-y-2">
                    <label className="block text-[9.5px] font-bold tracking-[0.12em] uppercase text-[#6F6A61]">
                      RÉPONSE STRUCTURÉE (CRITÈRES CLÉS, SEUILS & CONDUITE)
                    </label>
                    <textarea
                      rows={5}
                      disabled={Boolean(currentResult)}
                      value={writtenMap[currentQ.id] || ''}
                      onChange={(e) => setWrittenMap({ ...writtenMap, [currentQ.id]: e.target.value })}
                      placeholder="Rédigez votre réponse complète (mots-clés attendus par le correcteur)…"
                      className="w-full rounded-[4px] border border-[#D2C9B8] bg-[#FBF9F5] focus:bg-white focus:border-[#6B1D2F] p-3.5 text-[13px] text-[#161615] focus:outline-none disabled:opacity-80"
                    />
                  </div>
                ) : (
                  <div className="space-y-2.5">
                    {currentQ.options_json.map((opt) => {
                      const chosen = currentSelected.includes(opt.letter);
                      const showKey = Boolean(currentResult);
                      const isCorr = currentQ.correct_answers_json.includes(opt.letter);

                      let boxCls = 'bg-white border-[#E5DFD3] hover:border-[#D2C9B8]';
                      let badgeCls = 'bg-[#F3EFE7] border border-[#D2C9B8] text-[#161615]';
                      let txtCls = 'text-[#161615]';

                      if (!showKey && chosen) {
                        boxCls = 'bg-[#FBF5EE] border-[#9A7438] ring-1 ring-[#9A7438]';
                        badgeCls = 'bg-[#9A7438] border border-[#9A7438] text-white';
                        txtCls = 'text-[#161615] font-semibold';
                      } else if (showKey) {
                        if (isCorr && chosen) {
                          boxCls = 'bg-[#EFF5F2] border-[#2A5C48] ring-1 ring-[#2A5C48]';
                          badgeCls = 'bg-[#2A5C48] border border-[#2A5C48] text-white';
                          txtCls = 'text-[#2A5C48] font-bold';
                        } else if (isCorr && !chosen) {
                          boxCls = 'bg-[#FBF5EE] border-[#9A7438]';
                          badgeCls = 'bg-[#9A7438] border border-[#9A7438] text-white';
                          txtCls = 'text-[#9A7438] font-semibold';
                        } else if (!isCorr && chosen) {
                          boxCls = 'bg-[#FAF0F0] border-[#9E2A2B] ring-1 ring-[#9E2A2B]';
                          badgeCls = 'bg-[#9E2A2B] border border-[#9E2A2B] text-white';
                          txtCls = 'text-[#9E2A2B] font-semibold';
                        } else {
                          boxCls = 'bg-[#FBF9F5] border-[#E5DFD3] opacity-75';
                        }
                      }

                      return (
                        <button
                          key={opt.letter}
                          onClick={() => toggleOption(currentQ, opt.letter)}
                          disabled={showKey}
                          className={`w-full text-left px-3.5 py-3 rounded-[4px] border transition flex items-center gap-3.5 cursor-pointer ${boxCls}`}
                        >
                          <span
                            className={`w-[26px] h-[26px] rounded-[3px] font-mono-tabular text-[11px] font-bold flex items-center justify-center shrink-0 ${badgeCls}`}
                          >
                            {opt.letter}
                          </span>
                          <span className={`text-[13px] flex-1 leading-snug ${txtCls}`}>{opt.text}</span>
                          {showKey && isCorr && <CheckCircle2 className="w-4 h-4 text-[#2A5C48] shrink-0" />}
                          {showKey && !isCorr && chosen && (
                            <XCircle className="w-4 h-4 text-[#9E2A2B] shrink-0" />
                          )}
                        </button>
                      );
                    })}
                  </div>
                )}

                {/* Action Row */}
                <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-[#E5DFD3]">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setActiveQIdx((i) => Math.max(0, i - 1))}
                      disabled={activeQIdx === 0}
                      className="inline-flex items-center gap-1.5 px-3 py-2 rounded-[4px] bg-[#F3EFE7] border border-[#D2C9B8] disabled:opacity-40 text-xs font-semibold text-[#161615] cursor-pointer"
                    >
                      <ArrowLeft className="w-3.5 h-3.5" /> Précédente
                    </button>
                    <button
                      onClick={() => setActiveQIdx((i) => Math.min(questions.length - 1, i + 1))}
                      disabled={activeQIdx >= questions.length - 1}
                      className="inline-flex items-center gap-1.5 px-3 py-2 rounded-[4px] bg-[#F3EFE7] border border-[#D2C9B8] disabled:opacity-40 text-xs font-semibold text-[#161615] cursor-pointer"
                    >
                      Suivante <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  <div className="flex items-center gap-2">
                    {currentResult ? (
                      <button
                        onClick={() => handleRetryQuestion(currentQ.id)}
                        className="inline-flex items-center gap-1.5 px-4 py-2 rounded-[4px] bg-[#F3EFE7] border border-[#D2C9B8] hover:border-[#9A7438] text-xs font-semibold text-[#161615] cursor-pointer"
                      >
                        <RotateCcw className="w-3.5 h-3.5" /> Refaire cette question
                      </button>
                    ) : (
                      <button
                        onClick={() => handleSubmit(currentQ)}
                        disabled={!canSubmit || submittingId === currentQ.id}
                        className="px-5 py-2.5 rounded-[5px] bg-[#6B1D2F] hover:bg-[#531523] disabled:opacity-40 text-white text-xs font-semibold transition cursor-pointer"
                      >
                        {submittingId === currentQ.id ? 'Correction…' : 'Valider ma réponse'}
                      </button>
                    )}
                  </div>
                </div>

                {/* Deep Explanation & Doc Evidence Debrief */}
                {currentResult && (
                  <div className="space-y-3 pt-2">
                    <div
                      className={`p-4 rounded-[4px] border border-l-4 space-y-2 ${
                        currentResult.is_correct
                          ? 'bg-[#EFF5F2] border-[#B8D4C8] border-l-[#2A5C48]'
                          : 'bg-[#FAF0F0] border-[#E5B8B8] border-l-[#9E2A2B]'
                      }`}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-wider">
                          {currentResult.is_correct ? (
                            <>
                              <CheckCircle2 className="w-4 h-4 text-[#2A5C48]" />
                              <span className="text-[#2A5C48]">Piège déjoué · Réponse exacte</span>
                            </>
                          ) : (
                            <>
                              <AlertTriangle className="w-4 h-4 text-[#9E2A2B]" />
                              <span className="text-[#9E2A2B]">
                                {currentResult.grading_note} · Réponse attendue :{' '}
                                {currentResult.correct_answers.join(', ') || 'Barème QROC'}
                              </span>
                            </>
                          )}
                        </div>
                        <span className="font-mono-tabular text-xs font-bold text-[#161615]">
                          {currentResult.partial_score} / {currentResult.max_score} pt
                        </span>
                      </div>

                      <p className="text-[13px] leading-relaxed text-[#161615]">
                        {currentResult.explanation || currentQ.explanation}
                      </p>

                      {isCurrentWritten && (currentResult.rubric?.points?.length || 0) > 0 && (
                        <div className="pt-2 border-t border-[#D2C9B8]/60 space-y-1.5">
                          <div className="text-[9.5px] font-bold tracking-[0.12em] uppercase text-[#6F6A61]">
                            CRITÈRES DU BARÈME OFFICIEL
                          </div>
                          <ul className="space-y-1 text-[12px]">
                            {(currentResult.rubric.points || []).map((pt, k) => {
                              const hit = (currentResult.matched_points || []).includes(pt);
                              return (
                                <li
                                  key={k}
                                  className={`flex items-start gap-2 ${
                                    hit ? 'text-[#2A5C48] font-semibold' : 'text-[#9E2A2B]'
                                  }`}
                                >
                                  <span className="font-bold">{hit ? '✓' : '✗'}</span>
                                  <span>{pt}</span>
                                </li>
                              );
                            })}
                          </ul>
                        </div>
                      )}
                    </div>

                    {(currentQ.doc_evidence || currentResult.doc_evidence) && (
                      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 rounded-[4px] bg-[#FBF5EE] border border-[#DFC9A6]">
                        <div className="flex items-start gap-2 text-[12px] text-[#7A5922]">
                          <FileText className="w-4 h-4 shrink-0 mt-0.5" />
                          <span>
                            <strong>Appui document :</strong>{' '}
                            {currentQ.doc_evidence || currentResult.doc_evidence}
                          </span>
                        </div>
                        {currentQ.course_id && (
                          <button
                            onClick={() =>
                              onNavigate('courses', {
                                module_id: currentQ.module_id,
                                selected_course_id: currentQ.course_id,
                              })
                            }
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[4px] bg-white border border-[#D2C9B8] hover:border-[#9A7438] text-[11px] font-semibold text-[#161615] cursor-pointer shrink-0"
                          >
                            <BookOpen className="w-3.5 h-3.5" /> Réviser ce cours
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )
      ) : (
        /* Cas Cliniques Complexes Grid */
        <div className="space-y-4">
          {cases.length === 0 ? (
            <div className="bg-white border border-[#E5DFD3] rounded-[5px] p-10 text-center font-serif-editorial italic text-lg text-[#6F6A61]">
              Aucun cas clinique complexe trouvé pour ce filtre.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {cases.map((c) => (
                <div
                  key={c.id}
                  className="bg-white border border-[#E5DFD3] hover:border-[#9A7438] rounded-[5px] p-6 flex flex-col justify-between gap-4 transition"
                >
                  <div className="space-y-2.5">
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <ModuleBadge moduleId={c.module_id} sub={c.sub_discipline} />
                      <span className="font-mono-tabular text-[10.5px] font-bold text-[#9E2A2B] bg-[#FAF0F0] border border-[#E5B8B8] px-2 py-0.5 rounded-[3px]">
                        {c.steps_json.length} étapes · {c.difficulty}
                      </span>
                    </div>

                    <h3 className="font-serif-editorial text-[20px] leading-snug text-[#161615] font-normal">
                      {c.title}
                    </h3>

                    <p className="text-[12.5px] text-[#6F6A61] line-clamp-3 leading-relaxed">
                      {c.patient_summary}
                    </p>

                    {c.doc_evidence && (
                      <div className="font-mono-tabular text-[10.5px] text-[#9A7438] font-medium line-clamp-1">
                        Cours : {c.doc_evidence}
                      </div>
                    )}
                  </div>

                  <div className="flex items-center justify-between pt-3 border-t border-[#E5DFD3]">
                    <div className="font-mono-tabular text-[11px] text-[#6F6A61]">
                      {c.best_ratio !== null && c.best_ratio !== undefined
                        ? `Meilleur score : ${Math.round(c.best_ratio * 100)}% (${c.attempt_count} essai)`
                        : 'Dossier complexe prêt'}
                    </div>
                    <button
                      onClick={() => setActiveCase(c)}
                      className="px-4 py-2 rounded-[4px] bg-[#6B1D2F] hover:bg-[#531523] text-white text-xs font-semibold transition cursor-pointer"
                    >
                      Prendre en charge →
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
