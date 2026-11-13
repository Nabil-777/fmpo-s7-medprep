import React, { useEffect, useRef, useState } from 'react';
import { CheckCircle2, Eye, Maximize2, ShieldAlert, X, XCircle } from 'lucide-react';
import { api } from '../api';
import type { AttemptResult, QuestionItem } from '../types';
import { ModuleBadge, VerificationBadge } from './shared';

interface Props {
  initialPreset?: {
    module_id?: string;
    source_label?: string;
    session?: string;
    course_id?: number;
    traps_only?: boolean;
  } | null;
}

const EXAM_PRESETS = [
  { short: 'APS 2025 (30 Q)', source_label: 'EXAMEN APS 2025 SN', durationMin: 60 },
  { short: 'Endocrino (22)', source_label: 'EXAMEN ENDOCRINO 2025 SN', durationMin: 25 },
  { short: 'Dermato (30)', source_label: 'EXAMEN DERMATO 2025 SN', durationMin: 30 },
  { short: 'Hémato-Onco (35)', source_label: 'EXAMEN HEMATO ONCO 2025 SN', durationMin: 45 },
  { short: 'Neuro Rédac (60m)', source_label: 'EXAMEN NEURO NEUROCHIR 2025 SN', durationMin: 60 },
  { short: 'Blanc Neuro (48 QROC)', source_label: 'EXAMEN BLANC NEURO 2025 (Corrigé)', durationMin: 60 },
];

export const ExamSimulatorView: React.FC<Props> = ({ initialPreset }) => {
  const [sources, setSources] = useState<any[]>([]);
  const [moduleFilter, setModuleFilter] = useState(initialPreset?.module_id || 'all');
  const [sourceFilter, setSourceFilter] = useState(initialPreset?.source_label || 'all');
  const [sessionFilter, setSessionFilter] = useState(initialPreset?.session || 'all');
  const [courseFilter, setCourseFilter] = useState<number | undefined>(initialPreset?.course_id);
  const [trapsOnly, setTrapsOnly] = useState(Boolean(initialPreset?.traps_only));
  const [verifiedOnly, setVerifiedOnly] = useState(true);
  const [shuffle, setShuffle] = useState(false);

  const [questions, setQuestions] = useState<QuestionItem[]>([]);
  const [totalAvailable, setTotalAvailable] = useState(0);
  const [idx, setIdx] = useState(0);
  const [timedMode, setTimedMode] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [selectedMap, setSelectedMap] = useState<Record<number, string[]>>({});
  const [writtenMap, setWrittenMap] = useState<Record<number, string>>({});
  const [resultsMap, setResultsMap] = useState<Record<number, AttemptResult>>({});
  const [showScanPeek, setShowScanPeek] = useState(false);
  const [scanZoomOpen, setScanZoomOpen] = useState(false);
  const [examFinished, setExamFinished] = useState(false);
  const sessionIdRef = useRef(`sess_${Date.now()}`);

  useEffect(() => {
    api.questionSources().then((res) => setSources(res.sources));
  }, []);

  const loadQuestions = async (
    overrides?: Partial<{
      module_id: string;
      source_label: string;
      session: string;
      course_id?: number;
      traps_only: boolean;
      verified_only: boolean;
      shuffle: boolean;
      durationMin?: number;
      timed?: boolean;
    }>,
  ) => {
    const mod = overrides?.module_id ?? moduleFilter;
    const src = overrides?.source_label ?? sourceFilter;
    const sess = overrides?.session ?? sessionFilter;
    const cid = overrides && 'course_id' in overrides ? overrides.course_id : courseFilter;
    const trap = overrides?.traps_only ?? trapsOnly;
    const ver = overrides?.verified_only ?? verifiedOnly;
    const shuf = overrides?.shuffle ?? shuffle;

    const res = await api.questions({
      module_id: mod,
      source_label: src,
      session: sess,
      course_id: cid || '',
      traps_only: trap,
      verified_only: ver,
      shuffle: shuf,
      limit: 60,
    });
    setQuestions(res.questions);
    setTotalAvailable(res.total);
    setIdx(0);
    setSelectedMap({});
    setWrittenMap({});
    setResultsMap({});
    setExamFinished(false);
    setShowScanPeek(false);
    setScanZoomOpen(false);
    sessionIdRef.current = `sess_${Date.now()}`;
    if (overrides?.timed && overrides.durationMin) {
      setTimedMode(true);
      setSecondsLeft(overrides.durationMin * 60);
    } else if (!overrides?.timed) {
      setTimedMode(false);
    }
  };

  useEffect(() => {
    loadQuestions();
  }, []);

  useEffect(() => {
    if (!timedMode || examFinished || secondsLeft <= 0) return;
    const t = setInterval(() => {
      setSecondsLeft((s) => {
        if (s <= 1) {
          setExamFinished(true);
          return 0;
        }
        return s - 1;
      });
    }, 1000);
    return () => clearInterval(t);
  }, [timedMode, examFinished, secondsLeft]);

  const currentQ = questions[idx];

  const toggleOption = (letter: string, isSingleGroup: boolean) => {
    if (!currentQ || (resultsMap[currentQ.id] && !timedMode)) return;
    const prev = selectedMap[currentQ.id] || [];
    const next = isSingleGroup
      ? [letter]
      : prev.includes(letter)
        ? prev.filter((x) => x !== letter)
        : [...prev, letter].sort();
    setSelectedMap({ ...selectedMap, [currentQ.id]: next });
  };

  const gradeCurrent = async (qItem: QuestionItem) => {
    const res = await api.attemptQuestion(qItem.id, {
      session_id: sessionIdRef.current,
      mode: timedMode ? 'timed_exam' : 'practice',
      selected_answers: selectedMap[qItem.id] || [],
      written_answer: writtenMap[qItem.id] || '',
    });
    setResultsMap((prev) => ({ ...prev, [qItem.id]: res }));
    return res;
  };

  const finishTimedExam = async () => {
    const newResults: Record<number, AttemptResult> = { ...resultsMap };
    for (const qItem of questions) {
      if (!newResults[qItem.id]) {
        newResults[qItem.id] = await api.attemptQuestion(qItem.id, {
          session_id: sessionIdRef.current,
          mode: timedMode ? 'timed_exam' : 'practice',
          selected_answers: selectedMap[qItem.id] || [],
          written_answer: writtenMap[qItem.id] || '',
        });
      }
    }
    setResultsMap(newResults);
    setExamFinished(true);
  };

  const answeredCount = Object.keys(resultsMap).length;
  const correctCount = Object.values(resultsMap).filter((r) => r.is_correct).length;
  const partialSum = Object.values(resultsMap).reduce((a, b) => a + b.partial_score, 0);

  const fmtTime = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${String(m).padStart(2, '0')} : ${String(s).padStart(2, '0')}`;
  };

  return (
    <div className="space-y-5">
      {/* Quiet Focus Exam Bar (Board 04) */}
      <div className="bg-white border border-[#E5DFD3] rounded-[5px] p-4 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div className="space-y-2.5 flex-1">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-[9px] font-bold tracking-[0.13em] uppercase text-[#9A7438]">
              SESSION OFFICIELLE · 2025 SN & ANNALES FMPO
            </span>
          </div>

          <div className="flex flex-wrap gap-2">
            {EXAM_PRESETS.map((p) => {
              const active = sourceFilter === p.source_label;
              return (
                <button
                  key={p.source_label}
                  onClick={() => {
                    setSourceFilter(p.source_label);
                    setModuleFilter('all');
                    setSessionFilter('all');
                    setTrapsOnly(false);
                    setCourseFilter(undefined);
                    loadQuestions({
                      module_id: 'all',
                      source_label: p.source_label,
                      session: 'all',
                      course_id: undefined,
                      traps_only: false,
                      durationMin: p.durationMin,
                      timed: true,
                    });
                  }}
                  className={`px-3 py-1 rounded-[3px] text-[10.5px] font-semibold border transition cursor-pointer ${
                    active
                      ? 'bg-[#6B1D2F] text-white border-[#6B1D2F]'
                      : 'bg-[#FBF9F5] text-[#6F6A61] border-[#D2C9B8] hover:border-[#9A7438] hover:text-[#161615]'
                  }`}
                >
                  {p.short}
                </button>
              );
            })}
          </div>

          <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-[#E5DFD3]">
            <select
              value={moduleFilter}
              onChange={(e) => setModuleFilter(e.target.value)}
              className="px-2.5 py-1 text-[11px] rounded-[4px] border border-[#D2C9B8] bg-[#FBF9F5] text-[#161615]"
            >
              <option value="all">Tous modules</option>
              <option value="anapath">Anapath APS</option>
              <option value="endocrino-dermato">Endocrino · Dermato</option>
              <option value="hemato-onco">Hémato · Onco</option>
              <option value="neuro-neurochir">Neuro · NeuroChir</option>
            </select>

            <select
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
              className="px-2.5 py-1 text-[11px] rounded-[4px] border border-[#D2C9B8] bg-[#FBF9F5] text-[#161615] max-w-[230px]"
            >
              <option value="all">Toutes les banques ({totalAvailable})</option>
              {sources.map((s) => (
                <option key={s.source_label} value={s.source_label}>
                  {s.source_label} ({s.total} Q)
                </option>
              ))}
            </select>

            <button
              onClick={() => {
                setCourseFilter(undefined);
                loadQuestions({ course_id: undefined, timed: false });
              }}
              className="px-3.5 py-1 rounded-[4px] bg-[#6B1D2F] hover:bg-[#531523] text-white text-[11px] font-semibold cursor-pointer transition"
            >
              Charger la série
            </button>
          </div>
        </div>

        {/* Right Countdown Block */}
        <div className="lg:pl-5 lg:border-l border-[#E5DFD3] shrink-0 flex items-center lg:flex-col lg:items-start justify-between gap-1">
          <span className="text-[9px] font-bold tracking-[0.11em] uppercase text-[#6F6A61]">
            {timedMode ? 'TEMPS RESTANT' : 'MODE LIBRE'}
          </span>
          <div className="font-mono-tabular text-[20px] font-bold text-[#6B1D2F]">
            {timedMode ? fmtTime(secondsLeft) : `${questions.length} Q`}
          </div>
        </div>
      </div>

      {/* Main 3-Col Reading Desk */}
      {questions.length === 0 ? (
        <div className="bg-white border border-[#E5DFD3] rounded-[5px] p-12 text-center text-sm text-[#6F6A61]">
          Aucune question ne correspond à ces filtres. Essayez « Toutes les banques » ou décochez
          « Corrigé vérifié SN ».
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
          {/* Left 3 Cols: Feuille de Coche & Filters */}
          <aside className="lg:col-span-3 bg-white border border-[#E5DFD3] rounded-[5px] p-4 space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-[9.5px] font-bold tracking-[0.13em] uppercase text-[#6F6A61]">
                FEUILLE DE COCHE
              </span>
              <span className="font-mono-tabular text-[10.5px] font-bold text-[#9A7438]">
                {String(idx + 1).padStart(2, '0')} / {String(questions.length).padStart(2, '0')}
              </span>
            </div>

            <div className="grid grid-cols-5 lg:grid-cols-4 gap-2 max-h-72 overflow-y-auto pr-0.5">
              {questions.map((qItem, i) => {
                const res = resultsMap[qItem.id];
                const hasChoice =
                  (selectedMap[qItem.id] && selectedMap[qItem.id].length > 0) ||
                  Boolean(writtenMap[qItem.id]?.trim());

                let btnCls = 'bg-[#FBF9F5] text-[#6F6A61] border-[#D2C9B8] hover:border-[#9A7438]';
                if (i === idx) {
                  btnCls = 'bg-[#6B1D2F] text-white border-[#6B1D2F]';
                } else if (res) {
                  btnCls = res.is_correct
                    ? 'bg-[#EFF5F2] text-[#2A5C48] border-[#2A5C48]'
                    : 'bg-[#FAF0F0] text-[#9E2A2B] border-[#9E2A2B]';
                } else if (hasChoice) {
                  btnCls = 'bg-[#FBF5EE] text-[#9A7438] border-[#9A7438]';
                }

                return (
                  <button
                    key={qItem.id}
                    onClick={() => setIdx(i)}
                    className={`h-[34px] rounded-[3px] border font-mono-tabular text-[11px] font-semibold transition cursor-pointer ${btnCls}`}
                  >
                    {String(qItem.question_number || i + 1).padStart(2, '0')}
                  </button>
                );
              })}
            </div>

            <div className="border-t border-[#E5DFD3] pt-3.5 space-y-2.5">
              <div className="text-[9px] font-bold tracking-[0.12em] uppercase text-[#6F6A61]">
                FILTRES D'ÉPREUVE
              </div>
              <label className="flex items-center gap-2 text-[11px] text-[#161615] cursor-pointer">
                <input
                  type="checkbox"
                  checked={verifiedOnly}
                  onChange={(e) => setVerifiedOnly(e.target.checked)}
                  className="accent-[#6B1D2F]"
                />
                <span>Corrigé vérifié uniquement</span>
              </label>
              <label className="flex items-center gap-2 text-[11px] text-[#6F6A61] cursor-pointer">
                <input
                  type="checkbox"
                  checked={trapsOnly}
                  onChange={(e) => setTrapsOnly(e.target.checked)}
                  className="accent-[#9E2A2B]"
                />
                <span>Mode Pièges marqués X</span>
              </label>
              <label className="flex items-center gap-2 text-[11px] text-[#6F6A61] cursor-pointer">
                <input
                  type="checkbox"
                  checked={shuffle}
                  onChange={(e) => setShuffle(e.target.checked)}
                  className="accent-[#6B1D2F]"
                />
                <span>Ordre aléatoire</span>
              </label>
            </div>

            {answeredCount > 0 && (
              <div className="border-t border-[#E5DFD3] pt-3 flex items-center justify-between text-[11px] font-mono-tabular text-[#6F6A61]">
                <span>Progression</span>
                <span className="font-bold text-[#2A5C48]">
                  {correctCount}/{answeredCount} ({partialSum.toFixed(1)} pts)
                </span>
              </div>
            )}

            {timedMode && !examFinished && (
              <button
                onClick={finishTimedExam}
                className="w-full py-2.5 rounded-[4px] bg-[#161615] hover:bg-[#2E2C29] text-white text-[11.5px] font-semibold transition cursor-pointer"
              >
                Rendre la copie
              </button>
            )}

            {examFinished && (
              <div className="p-3.5 rounded-[4px] bg-[#241116] border border-[#9A7438] text-[#FBF9F5] space-y-1">
                <div className="text-[9.5px] font-bold tracking-[0.14em] uppercase text-[#C7A46B]">
                  NOTE ESTIMÉE FMPO
                </div>
                <div className="font-serif-editorial text-[24px] tabular-nums">
                  {((correctCount / Math.max(1, questions.length)) * 20).toFixed(2)} / 20
                </div>
                <div className="font-mono-tabular text-[10.5px] text-[#D4C9BA]">
                  Justes : {correctCount}/{questions.length} · Partiel : {partialSum.toFixed(1)}/
                  {questions.length}
                </div>
              </div>
            )}
          </aside>

          {/* Center Printed Examination Sheet */}
          <div
            className={`space-y-4 ${
              showScanPeek && currentQ?.scan_page_image ? 'lg:col-span-5' : 'lg:col-span-9'
            }`}
          >
            {currentQ && (
              <div className="bg-white border border-[#E5DFD3] rounded-[5px] p-6 md:p-8 space-y-5">
                <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-[#E5DFD3]">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-[9.5px] font-bold tracking-[0.13em] uppercase text-[#9A7438]">
                      {currentQ.source_label} · QUESTION{' '}
                      {String(currentQ.question_number || idx + 1).padStart(2, '0')}
                    </span>
                    <ModuleBadge moduleId={currentQ.module_id} sub={currentQ.sub_discipline} />
                    <VerificationBadge status={currentQ.verification_status} />
                  </div>

                  {currentQ.scan_page_image && (
                    <button
                      onClick={() => setShowScanPeek((v) => !v)}
                      className="inline-flex items-center gap-1.5 px-3 py-1 rounded-[4px] bg-[#F3EFE7] border border-[#D2C9B8] hover:border-[#9A7438] text-[11px] font-semibold text-[#161615] transition cursor-pointer"
                    >
                      <Eye className="w-3.5 h-3.5 text-[#6F6A61]" />
                      {showScanPeek ? 'Masquer scan' : 'Voir scan original'}
                    </button>
                  )}
                </div>

                <div>
                  <h3 className="font-serif-editorial text-[25px] leading-snug font-normal text-[#161615]">
                    {currentQ.stem}
                  </h3>
                  {currentQ.course_title && (
                    <p className="text-[11.5px] text-[#6F6A61] mt-1.5">
                      Chapitre lié : {currentQ.course_title}
                      {currentQ.professor ? ` · ${currentQ.professor}` : ''}
                    </p>
                  )}
                </div>

                {currentQ.vignette_text && (
                  <div className="p-4 rounded-[4px] bg-[#F3EFE7] border border-[#D2C9B8] text-[13px] text-[#161615] leading-relaxed">
                    <div className="text-[9px] font-bold tracking-[0.12em] uppercase text-[#9A7438] mb-1">
                      CAS CLINIQUE / VIGNETTE
                    </div>
                    {currentQ.vignette_text}
                  </div>
                )}

                {currentQ.statements_json.length > 0 && (
                  <div className="rounded-[4px] bg-[#FBF9F5] border border-[#D2C9B8] p-4 space-y-2">
                    <div className="text-[9px] font-bold tracking-[0.12em] uppercase text-[#6F6A61]">
                      PROPOSITIONS A–E (CHOIX UNIQUE A–E)
                    </div>
                    {currentQ.statements_json.map((st) => (
                      <div key={st.letter} className="text-[12.5px] text-[#161615] flex gap-2.5">
                        <span className="font-semibold text-[#6F6A61] w-5 shrink-0">
                          {st.letter})
                        </span>
                        <span>{st.text}</span>
                      </div>
                    ))}
                  </div>
                )}

                {currentQ.question_type === 'qroc' || currentQ.question_type === 'synthesis' ? (
                  <div className="space-y-2">
                    <label className="block text-[9.5px] font-bold tracking-[0.12em] uppercase text-[#6F6A61]">
                      VOTRE RÉPONSE RÉDIGÉE (MOTS-CLÉS & CONDUITE)
                    </label>
                    <textarea
                      rows={6}
                      value={writtenMap[currentQ.id] || ''}
                      onChange={(e) =>
                        setWrittenMap({ ...writtenMap, [currentQ.id]: e.target.value })
                      }
                      placeholder="Rédigez votre réponse structurée (clinique, paraclinique, contre-indications, conduite à tenir)…"
                      className="w-full rounded-[4px] border border-[#D2C9B8] bg-[#FBF9F5] focus:bg-white focus:border-[#6B1D2F] p-3.5 text-[13px] text-[#161615] focus:outline-none"
                    />
                  </div>
                ) : (
                  <div className="space-y-2.5">
                    {currentQ.options_json.map((opt) => {
                      const sel = (selectedMap[currentQ.id] || []).includes(opt.letter);
                      const result = resultsMap[currentQ.id];
                      const showKey = Boolean(result) && (!timedMode || examFinished);
                      const isCorr = currentQ.correct_answers_json.includes(opt.letter);

                      let boxCls = 'bg-white border-[#E5DFD3] hover:border-[#D2C9B8]';
                      let badgeCls = 'bg-[#F3EFE7] border border-[#D2C9B8] text-[#161615]';
                      let txtCls = 'text-[#161615]';

                      if (!showKey && sel) {
                        boxCls = 'bg-[#FBF5EE] border-[#9A7438] ring-1 ring-[#9A7438]';
                        badgeCls = 'bg-[#9A7438] border border-[#9A7438] text-white';
                        txtCls = 'text-[#161615] font-semibold';
                      } else if (showKey) {
                        if (isCorr && sel) {
                          boxCls = 'bg-[#EFF5F2] border-[#2A5C48] ring-1 ring-[#2A5C48]';
                          badgeCls = 'bg-[#2A5C48] border border-[#2A5C48] text-white';
                          txtCls = 'text-[#2A5C48] font-bold';
                        } else if (isCorr && !sel) {
                          boxCls = 'bg-[#FBF5EE] border-[#9A7438]';
                          badgeCls = 'bg-[#9A7438] border border-[#9A7438] text-white';
                          txtCls = 'text-[#9A7438] font-semibold';
                        } else if (!isCorr && sel) {
                          boxCls = 'bg-[#FAF0F0] border-[#9E2A2B] ring-1 ring-[#9E2A2B]';
                          badgeCls = 'bg-[#9E2A2B] border border-[#9E2A2B] text-white';
                          txtCls = 'text-[#9E2A2B] font-semibold';
                        }
                      }

                      return (
                        <button
                          key={opt.letter}
                          onClick={() => toggleOption(opt.letter, currentQ.question_type === 'qcm_group')}
                          className={`w-full text-left px-3.5 py-3 rounded-[4px] border transition flex items-center gap-3.5 cursor-pointer ${boxCls}`}
                        >
                          <span
                            className={`w-[26px] h-[26px] rounded-[3px] font-mono-tabular text-[11px] font-bold flex items-center justify-center shrink-0 ${badgeCls}`}
                          >
                            {opt.letter}
                          </span>
                          <span className={`text-[13px] flex-1 leading-snug ${txtCls}`}>
                            {opt.text}
                          </span>
                          {showKey && isCorr && (
                            <CheckCircle2 className="w-4 h-4 text-[#2A5C48] shrink-0" />
                          )}
                          {showKey && !isCorr && sel && (
                            <XCircle className="w-4 h-4 text-[#9E2A2B] shrink-0" />
                          )}
                        </button>
                      );
                    })}
                  </div>
                )}

                {/* Navigation & Grade Footer */}
                <div className="flex flex-wrap items-center justify-between gap-3 pt-4 border-t border-[#E5DFD3]">
                  <button
                    disabled={idx <= 0}
                    onClick={() => setIdx((i) => Math.max(0, i - 1))}
                    className="px-4 py-2 rounded-[4px] bg-white border border-[#D2C9B8] hover:border-[#9A7438] text-[11.5px] font-semibold text-[#161615] disabled:opacity-40 cursor-pointer"
                  >
                    ← Précédente
                  </button>

                  <div className="flex items-center gap-2.5">
                    {!resultsMap[currentQ.id] && (
                      <button
                        onClick={() => gradeCurrent(currentQ)}
                        className="px-4 py-2 rounded-[4px] bg-[#161615] hover:bg-[#2F2C28] text-white text-[11.5px] font-semibold cursor-pointer transition"
                      >
                        {timedMode && !examFinished ? 'Enregistrer' : 'Corriger cette question'}
                      </button>
                    )}
                    <button
                      disabled={idx >= questions.length - 1}
                      onClick={() => setIdx((i) => Math.min(questions.length - 1, i + 1))}
                      className="px-4 py-2 rounded-[4px] bg-[#6B1D2F] hover:bg-[#531523] text-white text-[11.5px] font-semibold disabled:opacity-40 cursor-pointer transition"
                    >
                      Suivante →
                    </button>
                  </div>
                </div>

                {/* Result Feedback */}
                {resultsMap[currentQ.id] && (!timedMode || examFinished) && (
                  <div className="space-y-3 pt-2">
                    <div
                      className={`p-4 rounded-[4px] border text-[12.5px] ${
                        resultsMap[currentQ.id].is_correct
                          ? 'bg-[#EFF5F2] border-[#B8D4C8] text-[#161615]'
                          : 'bg-[#FAF0F0] border-[#DFC0C0] text-[#161615]'
                      }`}
                    >
                      <div className="font-bold flex items-center justify-between">
                        <span
                          className={
                            resultsMap[currentQ.id].is_correct
                              ? 'text-[#2A5C48]'
                              : 'text-[#9E2A2B]'
                          }
                        >
                          {resultsMap[currentQ.id].grading_note}
                        </span>
                        <span className="font-mono-tabular text-xs font-bold">
                          {resultsMap[currentQ.id].partial_score} / {resultsMap[currentQ.id].max_score}
                        </span>
                      </div>
                      {currentQ.explanation && (
                        <p className="mt-2 text-xs text-[#6F6A61] leading-relaxed whitespace-pre-line">
                          {currentQ.explanation}
                        </p>
                      )}
                    </div>

                    {resultsMap[currentQ.id].matched_points &&
                      (resultsMap[currentQ.id].matched_points!.length > 0 ||
                        resultsMap[currentQ.id].missed_points!.length > 0) && (
                        <div className="rounded-[4px] border border-[#D2C9B8] bg-[#FBF9F5] p-4 space-y-2 text-xs">
                          <div className="text-[9.5px] font-bold tracking-[0.12em] uppercase text-[#6F6A61]">
                            GRILLE DE CORRECTION OFFICIELLE
                          </div>
                          {resultsMap[currentQ.id].matched_points!.map((p, i) => (
                            <div key={i} className="flex items-start gap-2 text-[#2A5C48]">
                              <CheckCircle2 className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                              <span>{p}</span>
                            </div>
                          ))}
                          {resultsMap[currentQ.id].missed_points!.map((p, i) => (
                            <div key={i} className="flex items-start gap-2 text-[#9A7438]">
                              <ShieldAlert className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                              <span>À ajouter : {p}</span>
                            </div>
                          ))}
                        </div>
                      )}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Right Archival Darkroom Scan Proof Panel (Board 04) */}
          {showScanPeek && currentQ?.scan_page_image && (
            <aside className="lg:col-span-4 bg-[#191715] border border-[#2F2B26] rounded-[5px] p-5 text-[#FBF9F5] sticky top-24 space-y-4">
              <div>
                <div className="text-[9.5px] font-bold tracking-[0.13em] uppercase text-[#C7A46B]">
                  ARCHIVE NUMÉRISÉE · {currentQ.source_label}
                </div>
                <div className="text-[11.5px] text-[#B8B0A4] mt-0.5">
                  Copie originale annotée · Q{currentQ.question_number || idx + 1}
                </div>
              </div>

              <div className="bg-[#FBF9F5] p-1.5 rounded-[3px]">
                <img
                  src={currentQ.scan_page_image}
                  alt="Scan examen original"
                  className="w-full rounded-[2px] max-h-[54vh] object-contain"
                />
              </div>

              {currentQ.explanation && (
                <div className="space-y-1">
                  <div className="text-[9.5px] font-bold tracking-[0.12em] uppercase text-[#C7A46B]">
                    COMMENTAIRE DU CORRIGÉ
                  </div>
                  <p className="text-[11.5px] text-[#E5DFD3] leading-relaxed">
                    {currentQ.explanation}
                  </p>
                </div>
              )}

              <button
                onClick={() => setScanZoomOpen(true)}
                className="w-full py-2.5 rounded-[4px] bg-[#292521] border border-[#4A433B] hover:border-[#9A7438] text-[#FBF9F5] text-[11.5px] font-semibold inline-flex items-center justify-center gap-2 transition cursor-pointer"
              >
                <Maximize2 className="w-3.5 h-3.5 text-[#C7A46B]" /> Agrandir le scan original
              </button>
            </aside>
          )}
        </div>
      )}

      {/* Fullscreen Scan Lightbox */}
      {scanZoomOpen && currentQ?.scan_page_image && (
        <div
          className="fixed inset-0 z-50 bg-[#191715]/85 flex items-center justify-center p-4"
          onClick={() => setScanZoomOpen(false)}
        >
          <div
            className="relative max-w-4xl w-full bg-[#191715] border border-[#9A7438] rounded-[6px] p-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-3 text-[#FBF9F5]">
              <span className="font-mono-tabular text-xs text-[#C7A46B]">
                {currentQ.source_label} · Q{currentQ.question_number || idx + 1}
              </span>
              <button
                onClick={() => setScanZoomOpen(false)}
                className="p-1 text-[#D4C9BA] hover:text-white cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <img
              src={currentQ.scan_page_image}
              alt="Scan agrandi"
              className="w-full max-h-[82vh] object-contain bg-white rounded-[3px]"
            />
          </div>
        </div>
      )}
    </div>
  );
};
