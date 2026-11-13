import React, { useState } from 'react';
import { ArrowRight, CheckCircle2, FileText, RotateCcw, XCircle } from 'lucide-react';
import { api } from '../api';
import type { ClinicalCaseItem, NavTab } from '../types';
import { ModuleBadge } from './shared';

interface Props {
  activeCase: ClinicalCaseItem;
  backLabel: string;
  onBack: () => void;
  onAttemptRecorded?: () => void;
  onNavigate: (tab: NavTab, preset?: any) => void;
}

const VITAL_DOT_COLOR = (k: string, v: string): string => {
  const key = k.toLowerCase();
  const val = String(v).toLowerCase();
  if (key.includes('pa') && (val.includes('19') || val.includes('20') || val.includes('18') || val.includes('80/'))) {
    return '#9E2A2B';
  }
  if (key.includes('nihss') || key.includes('score') || key.includes('calc')) return '#6B1D2F';
  if (key.includes('spo2') || key.includes('sat') || key.includes('temp')) return '#2A5C48';
  return '#9A7438';
};

export const ClinicalCasePlayer: React.FC<Props> = ({
  activeCase,
  backLabel,
  onBack,
  onAttemptRecorded,
  onNavigate,
}) => {
  const [stepIdx, setStepIdx] = useState(0);
  const [selected, setSelected] = useState<Record<number, string[]>>({});
  const [validatedSteps, setValidatedSteps] = useState<Record<number, boolean>>({});
  const [totalScore, setTotalScore] = useState(0);
  const [completed, setCompleted] = useState(false);

  const resetCase = () => {
    setStepIdx(0);
    setSelected({});
    setValidatedSteps({});
    setTotalScore(0);
    setCompleted(false);
  };

  const step = activeCase.steps_json[stepIdx];
  if (!step) return null;

  const isStepValidated = Boolean(validatedSteps[stepIdx]);
  const currentSel = selected[stepIdx] || [];
  const maxTotal = activeCase.steps_json.reduce((acc, s) => acc + s.points, 0);
  const vitalEntries = Object.entries(activeCase.vitals_json || {});

  const toggleOpt = (letter: string) => {
    if (isStepValidated) return;
    const cur = new Set(currentSel);
    if (cur.has(letter)) cur.delete(letter);
    else cur.add(letter);
    setSelected({ ...selected, [stepIdx]: Array.from(cur) });
  };

  const validateStep = () => {
    const uSet = new Set(currentSel);
    const cSet = new Set(step.correct_answers);
    const exact = uSet.size === cSet.size && [...cSet].every((x) => uSet.has(x));
    const intersection = [...uSet].filter((x) => cSet.has(x)).length;
    const wrongPicks = [...uSet].filter((x) => !cSet.has(x)).length;
    const gained = exact
      ? step.points
      : Math.max(
          0,
          Number(
            ((intersection / Math.max(1, cSet.size) - wrongPicks * 0.25) * step.points).toFixed(2),
          ),
        );
    const newTotal = Number((totalScore + gained).toFixed(2));
    setTotalScore(newTotal);
    setValidatedSteps({ ...validatedSteps, [stepIdx]: true });

    if (stepIdx === activeCase.steps_json.length - 1) {
      setCompleted(true);
      api
        .recordCaseAttempt(activeCase.id, newTotal, maxTotal, {
          ...selected,
          [stepIdx]: currentSel,
        })
        .then(() => {
          if (onAttemptRecorded) onAttemptRecorded();
        });
    }
  };

  const nextStep = () => {
    if (stepIdx < activeCase.steps_json.length - 1) {
      setStepIdx(stepIdx + 1);
    }
  };

  return (
    <div className="space-y-5">
      {/* Architectural Step Ribbon (Board 03) */}
      <div className="bg-white border border-[#E5DFD3] rounded-[4px] px-5 py-3 flex flex-wrap items-center justify-between gap-4">
        <button
          onClick={onBack}
          className="text-[11.5px] font-semibold text-[#6F6A61] hover:text-[#161615] transition cursor-pointer"
        >
          ← {backLabel}
        </button>

        <div className="flex flex-wrap items-center gap-3">
          {activeCase.steps_json.map((s, i) => {
            const isCur = i === stepIdx;
            const isDone = Boolean(validatedSteps[i]);
            return (
              <React.Fragment key={s.step_number}>
                {i > 0 && <span className="hidden sm:inline-block w-7 h-[1px] bg-[#D2C9B8]" />}
                <button
                  onClick={() => (isDone || i <= stepIdx ? setStepIdx(i) : undefined)}
                  className={`inline-flex items-center gap-2 text-[11px] transition ${
                    isCur
                      ? 'font-bold text-[#6B1D2F]'
                      : isDone
                        ? 'font-semibold text-[#2A5C48] cursor-pointer'
                        : 'font-medium text-[#6F6A61]'
                  }`}
                >
                  <span
                    className="w-2.5 h-2.5 rounded-full shrink-0"
                    style={{
                      backgroundColor: isCur ? '#6B1D2F' : isDone ? '#2A5C48' : '#D2C9B8',
                    }}
                  />
                  <span>
                    {String(i + 1).padStart(2, '0')}. {s.step_type.replace('_', ' ')}
                  </span>
                </button>
              </React.Fragment>
            );
          })}
        </div>

        <div className="font-mono-tabular text-[10.5px] font-bold text-[#161615]">
          NOTE DOSSIER : {totalScore} / {maxTotal} PTS
        </div>
      </div>

      {/* Case Header + Quiet Bedside Telemetry Strip */}
      <div className="bg-white border border-[#E5DFD3] rounded-[5px] p-6 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="text-[9.5px] font-bold tracking-[0.14em] uppercase text-[#9A7438]">
            DOSSIER {activeCase.sub_discipline.toUpperCase()} · {activeCase.source_tag.toUpperCase()} · DIFFICULTÉ{' '}
            {activeCase.difficulty.toUpperCase()}
          </div>
          <ModuleBadge moduleId={activeCase.module_id} sub={activeCase.sub_discipline} />
        </div>

        <h2 className="font-serif-editorial text-[26px] leading-snug font-normal text-[#161615]">
          {activeCase.title}
        </h2>

        <p className="text-[13px] text-[#6F6A61] leading-relaxed">{activeCase.patient_summary}</p>

        {activeCase.doc_evidence && (
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-[4px] bg-[#FBF5EE] border border-[#DFC9A6] text-[11.5px] text-[#7A5922]">
            <FileText className="w-3.5 h-3.5 shrink-0" />
            <span>Appui documentaire : {activeCase.doc_evidence}</span>
          </div>
        )}

        {vitalEntries.length > 0 && (
          <div className="bg-[#F3EFE7] border border-[#D2C9B8] rounded-[4px] grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 divide-y sm:divide-y-0 sm:divide-x divide-[#D2C9B8]">
            {vitalEntries.map(([k, v]) => (
              <div key={k} className="px-4 py-2.5">
                <div className="flex items-center gap-1.5">
                  <span
                    className="w-1.5 h-1.5 rounded-full shrink-0"
                    style={{ backgroundColor: VITAL_DOT_COLOR(k, v) }}
                  />
                  <span className="text-[9px] font-bold tracking-[0.08em] uppercase text-[#6F6A61] truncate">
                    {k}
                  </span>
                </div>
                <div className="font-mono-tabular text-[12.5px] font-bold text-[#161615] mt-1">
                  {v}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Main 12-Col Split: Decision Card (Left 8) + Semeiology & Vigilance (Right 4) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        <div className="lg:col-span-8 bg-white border border-[#E5DFD3] rounded-[5px] p-6 space-y-5">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[9.5px] font-bold tracking-[0.14em] uppercase text-[#9A7438]">
              DÉCISION {String(step.step_number).padStart(2, '0')} ·{' '}
              {step.step_type.replace('_', ' ').toUpperCase()}
            </span>
            <span className="font-mono-tabular text-[10.5px] font-semibold text-[#6F6A61]">
              {step.points} pts
            </span>
          </div>

          <h3 className="font-serif-editorial text-[21px] leading-snug font-normal text-[#161615]">
            {step.prompt}
          </h3>

          <div className="space-y-2.5">
            {step.options.map((opt) => {
              const chosen = currentSel.includes(opt.letter);
              const isCorr = step.correct_answers.includes(opt.letter);

              let cardCls = 'bg-white border-[#E5DFD3] hover:border-[#D2C9B8]';
              let keyCls = 'bg-[#F3EFE7] border border-[#D2C9B8] text-[#161615]';
              let textCls = 'text-[#161615]';

              if (!isStepValidated && chosen) {
                cardCls = 'bg-[#FBF5EE] border-[#9A7438] ring-1 ring-[#9A7438]';
                keyCls = 'bg-[#9A7438] border border-[#9A7438] text-white';
                textCls = 'text-[#161615] font-semibold';
              } else if (isStepValidated) {
                if (isCorr && chosen) {
                  cardCls = 'bg-[#EFF5F2] border-[#2A5C48] ring-1 ring-[#2A5C48]';
                  keyCls = 'bg-[#2A5C48] border border-[#2A5C48] text-white';
                  textCls = 'text-[#2A5C48] font-bold';
                } else if (isCorr && !chosen) {
                  cardCls = 'bg-[#FBF5EE] border-[#9A7438]';
                  keyCls = 'bg-[#9A7438] border border-[#9A7438] text-white';
                  textCls = 'text-[#9A7438] font-semibold';
                } else if (!isCorr && chosen) {
                  cardCls = 'bg-[#FAF0F0] border-[#9E2A2B] ring-1 ring-[#9E2A2B]';
                  keyCls = 'bg-[#9E2A2B] border border-[#9E2A2B] text-white';
                  textCls = 'text-[#9E2A2B] font-semibold';
                } else {
                  cardCls = 'bg-[#FBF9F5] border-[#E5DFD3] opacity-70';
                }
              }

              return (
                <button
                  key={opt.letter}
                  onClick={() => toggleOpt(opt.letter)}
                  disabled={isStepValidated}
                  className={`w-full text-left px-4 py-3.5 rounded-[4px] border transition flex items-center gap-3.5 cursor-pointer ${cardCls}`}
                >
                  <span
                    className={`w-[26px] h-[26px] rounded-[3px] font-mono-tabular text-[11px] font-bold flex items-center justify-center shrink-0 ${keyCls}`}
                  >
                    {opt.letter}
                  </span>
                  <span className={`text-[13px] flex-1 leading-snug ${textCls}`}>{opt.text}</span>
                  {isStepValidated && isCorr && (
                    <span className="inline-flex items-center gap-1 text-[11px] font-bold text-[#2A5C48] shrink-0">
                      <CheckCircle2 className="w-4 h-4" />
                      {chosen && 'Validé'}
                    </span>
                  )}
                  {isStepValidated && !isCorr && chosen && (
                    <XCircle className="w-4 h-4 text-[#9E2A2B] shrink-0" />
                  )}
                </button>
              );
            })}
          </div>

          {isStepValidated && (
            <div className="bg-[#FBF9F5] border border-[#D2C9B8] border-l-4 border-l-[#2A5C48] rounded-[4px] p-4 space-y-1.5">
              <div className="text-[9.5px] font-bold tracking-[0.12em] uppercase text-[#2A5C48]">
                PERLE CLINIQUE · RÉPONSES {step.correct_answers.join(', ')}
              </div>
              <p className="text-[12.5px] leading-relaxed text-[#161615]">{step.teaching_pearl}</p>
            </div>
          )}

          <div className="flex justify-end pt-2">
            {!isStepValidated ? (
              <button
                onClick={validateStep}
                disabled={currentSel.length === 0}
                className="px-5 py-2.5 rounded-[5px] bg-[#6B1D2F] hover:bg-[#531523] disabled:opacity-40 text-white text-xs font-semibold transition cursor-pointer"
              >
                Valider cette conduite clinique
              </button>
            ) : (
              stepIdx < activeCase.steps_json.length - 1 && (
                <button
                  onClick={nextStep}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-[5px] bg-[#6B1D2F] hover:bg-[#531523] text-white text-xs font-semibold transition cursor-pointer"
                >
                  <span>Étape suivante</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              )
            )}
          </div>
        </div>

        {/* Right 4 Cols: Éléments séméiologiques + Vigilance & réflexes */}
        <div className="lg:col-span-4 space-y-4">
          <div className="bg-[#F3EFE7] border border-[#D2C9B8] rounded-[5px] p-5 space-y-3.5">
            <h4 className="font-serif-editorial italic text-[19px] text-[#161615] font-normal pb-2.5 border-b border-[#D2C9B8]">
              Éléments séméiologiques
            </h4>
            <p className="text-[12.5px] leading-relaxed text-[#161615]">{step.clinical_reveal}</p>
            {activeCase.course_id && (
              <button
                onClick={() =>
                  onNavigate('courses', {
                    module_id: activeCase.module_id,
                    selected_course_id: activeCase.course_id,
                  })
                }
                className="w-full py-2 px-3 rounded-[4px] bg-white border border-[#D2C9B8] hover:border-[#9A7438] text-[11.5px] font-semibold text-[#161615] transition cursor-pointer"
              >
                Consulter le cours {activeCase.course_title ? `(${activeCase.course_title})` : 'associé'}
              </button>
            )}
          </div>

          <div className="bg-[#FAF0F0] border border-[#DFC0C0] rounded-[5px] p-5 space-y-3">
            <h4 className="font-serif-editorial italic text-[19px] text-[#9E2A2B] font-normal pb-2.5 border-b border-[#DFC0C0]">
              Vigilance & réflexes d'urgence
            </h4>
            {isStepValidated && step.red_flags.length > 0 ? (
              <ul className="space-y-2.5 text-[12px] text-[#161615]">
                {step.red_flags.map((rf, i) => (
                  <li key={i} className="leading-relaxed">
                    <span className="font-bold text-[#9E2A2B]">{i + 1}.</span> {rf}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-[12px] leading-relaxed text-[#6F6A61]">
                {isStepValidated
                  ? 'Aucun piège critique additionnel signalé pour cette étape.'
                  : 'Les réflexes critiques d’urgence et contre-indications seront révélés dès la validation de votre décision.'}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Luxury Completion Summary */}
      {completed && (
        <div className="bg-[#241116] border border-[#9A7438] rounded-[6px] p-6 text-[#FBF9F5] space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="text-[9.5px] font-bold tracking-[0.16em] uppercase text-[#C7A46B]">
                DOSSIER CLINIQUE CLÔTURÉ
              </div>
              <h3 className="font-serif-editorial text-[24px] font-normal mt-1">
                Score final : {totalScore} / {maxTotal} points ({Math.round((totalScore / maxTotal) * 100)}%)
              </h3>
            </div>
            <button
              onClick={resetCase}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-[4px] bg-[#9A7438] hover:bg-[#AD8340] text-[#19120B] text-xs font-semibold transition cursor-pointer"
            >
              <RotateCcw className="w-3.5 h-3.5" /> Recommencer le dossier
            </button>
          </div>
          <div className="border-t border-[#44252D] pt-4">
            <div className="text-[9.5px] font-bold tracking-[0.14em] uppercase text-[#C7A46B] mb-2">
              SYNTHÈSE RÉFLEXE À RETENIR
            </div>
            <ul className="space-y-1.5 text-[13px] text-[#E5DFD3] list-disc pl-5">
              {activeCase.takeaway_points.map((tp, i) => (
                <li key={i}>{tp}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
};
