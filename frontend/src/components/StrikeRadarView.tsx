import React, { useEffect, useState } from 'react';
import { api } from '../api';
import type { NavTab } from '../types';
import { ModuleBadge, UploadFlagBadge } from './shared';

interface Props {
  onNavigate: (tab: NavTab, preset?: any) => void;
}

export const StrikeRadarView: React.FC<Props> = ({ onNavigate }) => {
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    api.radar().then(setData);
  }, []);

  if (!data) {
    return (
      <div className="py-16 text-center font-serif-editorial italic text-lg text-[#6F6A61]">
        Chargement du Radar Annales & Professeurs…
      </div>
    );
  }

  const { banks, hot_courses, sn2025_traps } = data;
  const maxQ = Math.max(1, ...(hot_courses || []).map((h: any) => h.sn_count || h.q_count || 1));

  return (
    <div className="space-y-6">
      {/* Editorial Radar Header (Board 06) */}
      <div className="bg-white border border-[#E5DFD3] rounded-[5px] p-6 flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-1 max-w-3xl">
          <div className="text-[9.5px] font-bold tracking-[0.15em] uppercase text-[#9A7438]">
            ANALYTIQUE DES ANNALES & SUIVI EXAMENS S7
          </div>
          <h2 className="font-serif-editorial text-[24px] leading-snug font-normal text-[#161615]">
            Radar Stratégique des Sujets &{' '}
            <span className="italic text-[#6B1D2F]">Pièges Marqués 2025 SN</span>
          </h2>
          <p className="text-[12.5px] text-[#6F6A61]">
            Repérez les chapitres les plus récurrents entre QE Professeurs, Examens Blancs (6/8
            QROC Neuro SN 2025 issues de l’Examen Blanc) et questions piégeuses marquées X.
          </p>
        </div>

        <button
          onClick={() => onNavigate('exams', { traps_only: true })}
          className="px-5 py-2.5 rounded-[4px] bg-[#9E2A2B] hover:bg-[#822021] text-white text-xs font-semibold transition cursor-pointer shrink-0"
        >
          Réviser {sn2025_traps.length} Pièges X
        </button>
      </div>

      {/* Left Banks Table + Right Recurrence Ledger */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        <div className="lg:col-span-7 bg-white border border-[#E5DFD3] rounded-[5px] p-5 space-y-3">
          <div className="text-[9.5px] font-bold tracking-[0.13em] uppercase text-[#6F6A61]">
            COUVERTURE PAR BANQUE D'ANNALES ET PROFESSEUR
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="border-b border-[#D2C9B8] text-[9.5px] font-bold uppercase tracking-wider text-[#6F6A61]">
                  <th className="py-2.5 pr-3">Banque / Épreuve</th>
                  <th className="py-2.5 pr-3">Pièges</th>
                  <th className="py-2.5 pr-3">Module</th>
                  <th className="py-2.5 pr-3 text-right">Corrigées</th>
                  <th className="py-2.5 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E5DFD3]">
                {banks.map((b: any) => (
                  <tr key={`${b.source_label}-${b.module_id}`} className="hover:bg-[#FBF9F5]">
                    <td className="py-3 pr-3 font-semibold text-[#161615]">{b.source_label}</td>
                    <td className="py-3 pr-3">
                      {b.trap_count > 0 ? (
                        <span className="inline-flex px-2 py-0.5 rounded-[3px] bg-[#FAF0F0] border border-[#E5B8B8] text-[#9E2A2B] font-mono-tabular text-[10px] font-bold">
                          {b.trap_count} X
                        </span>
                      ) : (
                        <span className="inline-flex px-2 py-0.5 rounded-[3px] bg-[#F3EFE7] border border-[#E5DFD3] text-[#6F6A61] font-mono-tabular text-[10px]">
                          —
                        </span>
                      )}
                    </td>
                    <td className="py-3 pr-3">
                      <ModuleBadge moduleId={b.module_id} />
                    </td>
                    <td className="py-3 pr-3 text-right font-mono-tabular font-bold text-[#2A5C48] whitespace-nowrap">
                      {b.keyed_count} / {b.question_count}
                    </td>
                    <td className="py-3 text-right">
                      <button
                        onClick={() => onNavigate('exams', { source_label: b.source_label })}
                        className="px-3 py-1 rounded-[4px] bg-[#FBF9F5] border border-[#D2C9B8] hover:border-[#6B1D2F] text-[#161615] text-[11px] font-semibold transition cursor-pointer"
                      >
                        Lancer
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right High-Yield Leaderboard */}
        <div className="lg:col-span-5 bg-white border border-[#E5DFD3] rounded-[5px] p-5 space-y-3">
          <div className="text-[9.5px] font-bold tracking-[0.13em] uppercase text-[#6F6A61]">
            PALMARÈS DE RÉCURRENCE · SN 2025
          </div>

          <div className="divide-y divide-[#E5DFD3] max-h-[540px] overflow-y-auto pr-1">
            {hot_courses.map((hc: any, i: number) => {
              const weightVal = hc.sn_count > 0 ? hc.sn_count : hc.q_count;
              const pct = Math.min(100, Math.max(12, Math.round((weightVal / maxQ) * 100)));
              return (
                <button
                  key={hc.id}
                  onClick={() =>
                    onNavigate('courses', { module_id: hc.module_id, selected_course_id: hc.id })
                  }
                  className="w-full py-3.5 text-left hover:bg-[#FBF9F5] -mx-2 px-2 rounded-[4px] transition cursor-pointer space-y-2"
                >
                  <div className="flex items-baseline justify-between gap-3">
                    <div className="flex items-baseline gap-3 min-w-0">
                      <span className="font-serif-editorial italic text-[16px] text-[#9A7438] shrink-0">
                        {String(i + 1).padStart(2, '0')}
                      </span>
                      <div className="min-w-0">
                        <div className="text-[12.5px] font-semibold text-[#161615] truncate">
                          {hc.canonical_title}
                        </div>
                        <div className="text-[11px] text-[#6F6A61] flex items-center gap-2 flex-wrap mt-0.5">
                          <span>{hc.professor}</span>
                          <UploadFlagBadge flag={hc.upload_flag} />
                        </div>
                      </div>
                    </div>

                    <span className="font-mono-tabular text-[10.5px] font-bold text-[#6B1D2F] shrink-0">
                      {hc.sn_count > 0 ? `${hc.sn_count} en SN 2025` : `${hc.q_count} Q`}
                    </span>
                  </div>

                  <div className="pl-7">
                    <div className="h-[3px] w-full rounded-[1.5px] bg-[#E5DFD3] overflow-hidden">
                      <div
                        className="h-full bg-[#9A7438] rounded-[1.5px]"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Bottom Flagged Traps Dossier */}
      <div className="bg-white border border-[#E5DFD3] rounded-[5px] p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-[#E5DFD3] pb-3">
          <div>
            <div className="text-[9.5px] font-bold tracking-[0.13em] uppercase text-[#9E2A2B]">
              RELEVÉ CRITIQUE · COPIES EXAMEN 2025 SN
            </div>
            <h3 className="font-serif-editorial text-[20px] font-normal text-[#161615] mt-0.5">
              Pièges réels marqués « X » ({sn2025_traps.length})
            </h3>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
          {sn2025_traps.map((t: any) => (
            <div
              key={t.id}
              className="p-4 rounded-[4px] bg-[#FAF0F0] border border-[#E5B8B8] space-y-2"
            >
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <ModuleBadge moduleId={t.module_id} sub={t.sub_discipline} />
                <span className="font-mono-tabular text-[10.5px] font-bold text-[#9E2A2B]">
                  {t.source_label} · Q{t.question_number} · Rép :{' '}
                  {t.correct_answers_json.join(', ')}
                </span>
              </div>
              <div className="text-[13px] font-semibold text-[#161615]">{t.stem}</div>
              {t.explanation && (
                <div className="text-[11.5px] text-[#6F6A61] leading-relaxed">{t.explanation}</div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
