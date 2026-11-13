import React, { useState } from 'react';
import { CheckCircle2 } from 'lucide-react';
import type { ModuleInfo, NavTab } from '../types';
import { MODULE_ROMAN, UploadFlagBadge, sortModulesEditorial } from './shared';

interface Props {
  data: any;
  onNavigate: (tab: NavTab, preset?: any) => void;
}

const QUICK_LAUNCH_EXAMS = [
  { label: 'APS · 30 QCM', source: 'EXAMEN APS 2025 SN' },
  { label: 'Endocrino · 22', source: 'EXAMEN ENDOCRINO 2025 SN' },
  { label: 'Dermato · 30', source: 'EXAMEN DERMATO 2025 SN' },
  { label: 'Hémato · 35', source: 'EXAMEN HEMATO ONCO 2025 SN' },
];

export const DashboardView: React.FC<Props> = ({ data, onNavigate }) => {
  const [folioTab, setFolioTab] = useState<'priority' | 'alerts'>('priority');

  if (!data) {
    return (
      <div className="py-16 text-center font-serif-editorial italic text-lg text-[#6F6A61]">
        Préparation de l'édition S7…
      </div>
    );
  }

  const { summary, modules, due_courses, curriculum_alerts } = data as {
    summary: any;
    modules: ModuleInfo[];
    due_courses: any[];
    curriculum_alerts: any[];
  };

  const orderedModules = sortModulesEditorial(modules || []);
  const resumeCourse =
    (due_courses || []).find((c) => c.canonical_title?.toLowerCase().includes('behçet')) ||
    due_courses?.[0];

  return (
    <div className="space-y-8">
      {/* Top Editorial Hero + Direct SN Launch Strip (Board 02) */}
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <div className="lg:col-span-8 space-y-4">
          <div className="text-[9.5px] font-bold tracking-[0.18em] uppercase text-[#9A7438]">
            FACULTÉ DE MÉDECINE D'OUJDA · PROGRAMME RESTRUCTURÉ S7
          </div>

          <h1 className="font-serif-editorial text-[32px] sm:text-[38px] leading-[1.14] text-[#161615] font-normal">
            Préparez la <span className="italic text-[#6B1D2F]">septième session</span> avec
            précision.
          </h1>

          <p className="text-[13.5px] leading-relaxed text-[#6F6A61] max-w-2xl">
            Cinq épreuves numérisées de la session normale 2025, {summary.total_courses} chapitres
            indexés et {summary.total_cases} dossiers cliniques progressifs.
          </p>

          <div className="flex flex-wrap items-center gap-3 pt-1">
            <button
              onClick={() => onNavigate('exams', { session: 'SN' })}
              className="px-5 py-2.5 rounded-[5px] bg-[#6B1D2F] hover:bg-[#531523] text-white text-xs font-semibold transition cursor-pointer"
            >
              Simuler l'Examen 2025 SN
            </button>
            {resumeCourse ? (
              <button
                onClick={() =>
                  onNavigate('courses', {
                    module_id: resumeCourse.module_id,
                    selected_course_id: resumeCourse.id,
                  })
                }
                className="px-5 py-2.5 rounded-[5px] bg-white border border-[#D2C9B8] hover:border-[#9A7438] text-[#161615] text-xs font-semibold transition cursor-pointer"
              >
                Reprendre : {resumeCourse.canonical_title}
              </button>
            ) : (
              <button
                onClick={() => onNavigate('clinical')}
                className="px-5 py-2.5 rounded-[5px] bg-white border border-[#D2C9B8] hover:border-[#9A7438] text-[#161615] text-xs font-semibold transition cursor-pointer"
              >
                Situations Cliniques
              </button>
            )}
            <button
              onClick={() => onNavigate('possible')}
              className="px-5 py-2.5 rounded-[5px] bg-[#241116] border border-[#9A7438] hover:bg-[#3A1C24] text-[#FBF9F5] text-xs font-semibold transition cursor-pointer"
            >
              Possible Question ({summary.possible_questions ?? 0} Q · {summary.possible_cases ?? 0} Cas)
            </button>
            <button
              onClick={() => onNavigate('scans')}
              className="px-5 py-2.5 rounded-[5px] bg-[#F3EFE7] border border-[#D2C9B8] hover:bg-[#E9E2D4] text-[#161615] text-xs font-semibold transition cursor-pointer"
            >
              Studio Scans OCR
            </button>
          </div>
        </div>

        {/* Right Quick Launch Folio Box */}
        <div className="lg:col-span-4 bg-[#F3EFE7] border border-[#D2C9B8] rounded-[5px] p-5 space-y-3">
          <div className="text-[9.5px] font-bold tracking-[0.13em] uppercase text-[#6F6A61]">
            ACCÈS DIRECT · ÉPREUVES 2025 SN
          </div>
          <div className="grid grid-cols-2 gap-2.5">
            {QUICK_LAUNCH_EXAMS.map((q) => (
              <button
                key={q.source}
                onClick={() => onNavigate('exams', { source_label: q.source })}
                className="py-2.5 px-3 rounded-[4px] bg-white border border-[#D2C9B8] hover:border-[#6B1D2F] text-[#161615] text-[11px] font-semibold transition cursor-pointer"
              >
                {q.label}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* Architectural Hairline Stat Ribbon */}
      <section className="border-y border-[#D2C9B8] py-5 grid grid-cols-2 lg:grid-cols-4 gap-y-5 lg:gap-y-0 lg:divide-x divide-[#E5DFD3]">
        <div className="lg:pr-6">
          <div className="text-[9.5px] font-bold tracking-[0.13em] uppercase text-[#6F6A61]">
            QUESTIONS CORRIGÉES
          </div>
          <div className="font-serif-editorial text-[32px] leading-tight text-[#161615] mt-1">
            {Number(summary.ready_questions).toLocaleString('fr-FR')}
          </div>
          <div className="font-mono-tabular text-[10.5px] font-medium text-[#9A7438] mt-1">
            / {Number(summary.total_questions).toLocaleString('fr-FR')} · dont{' '}
            {summary.sn2025_questions} SN 2025
          </div>
        </div>

        <div className="lg:px-6">
          <div className="text-[9.5px] font-bold tracking-[0.13em] uppercase text-[#6F6A61]">
            PRÉCISION GLOBALE
          </div>
          <div className="font-serif-editorial text-[32px] leading-tight text-[#2A5C48] mt-1">
            {summary.overall_accuracy} %
          </div>
          <div className="font-mono-tabular text-[10.5px] font-medium text-[#6F6A61] mt-1">
            {summary.total_attempts} tentatives enregistrées
          </div>
        </div>

        <div className="lg:px-6">
          <div className="text-[9.5px] font-bold tracking-[0.13em] uppercase text-[#6F6A61]">
            SITUATIONS CLINIQUES
          </div>
          <div className="font-serif-editorial text-[32px] leading-tight text-[#161615] mt-1">
            {summary.cases_completed} / {summary.total_cases}
          </div>
          <div className="font-mono-tabular text-[10.5px] font-medium text-[#6F6A61] mt-1">
            Urgences & dossiers progressifs S7
          </div>
        </div>

        <div className="lg:pl-6">
          <div className="text-[9.5px] font-bold tracking-[0.13em] uppercase text-[#6F6A61]">
            PROGRAMME & SUPPORTS
          </div>
          <div className="font-serif-editorial text-[32px] leading-tight text-[#161615] mt-1">
            {summary.total_courses}
          </div>
          <div className="font-mono-tabular text-[10.5px] font-medium text-[#6F6A61] mt-1">
            {curriculum_alerts?.length || 0} alertes supports 2026–2027
          </div>
        </div>
      </section>

      {/* Main Split: 8 Cols Module Ledger + 4 Cols Velours Grenat Folio */}
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-7 items-start">
        {/* Left 8 Cols: Programme des Quatre Disciplines */}
        <div className="lg:col-span-8 space-y-3">
          <div className="flex items-center justify-between gap-2 pb-1">
            <span className="text-[10px] font-bold tracking-[0.16em] uppercase text-[#9A7438]">
              PROGRAMME DES QUATRE DISCIPLINES
            </span>
            <span className="text-[11px] text-[#6F6A61]">Barème officiel FMPO 2025 SN</span>
          </div>

          <div className="space-y-3">
            {orderedModules.map((m) => (
              <div
                key={m.id}
                className="bg-white border border-[#E5DFD3] hover:border-[#D2C9B8] rounded-[5px] px-6 py-5 flex flex-col sm:flex-row sm:items-center justify-between gap-5 transition"
              >
                <div className="min-w-0 flex-1 space-y-1.5">
                  <div className="flex items-baseline gap-3">
                    <span className="font-serif-editorial italic text-[20px] text-[#9A7438] shrink-0">
                      {MODULE_ROMAN[m.id] || '·'}
                    </span>
                    <h2 className="font-serif-editorial text-[20px] leading-snug text-[#161615] font-normal truncate">
                      {m.name}
                    </h2>
                  </div>
                  <p className="text-[11.5px] text-[#6F6A61]">
                    {m.exam_format} · {m.scoring_rule}
                  </p>
                  <div className="font-mono-tabular text-[10px] font-semibold text-[#9B9488] pt-0.5">
                    {m.exam_duration_min} min · {m.question_count} Q · {m.clinical_cases_count} Cas
                    {m.attempts_accuracy !== null ? ` · ${m.attempts_accuracy}% réussite` : ''}
                  </div>
                </div>

                <div className="flex sm:items-center gap-5 shrink-0 justify-between sm:justify-end">
                  <div className="w-[132px] space-y-1.5">
                    <div className="text-right font-mono-tabular text-[10px] font-semibold text-[#161615]">
                      Maîtrise {Math.round(m.course_mastery_avg)}%
                    </div>
                    <div className="h-[2.5px] w-full rounded-[1px] bg-[#E5DFD3] overflow-hidden">
                      <div
                        className="h-full bg-[#6B1D2F] rounded-[1px]"
                        style={{ width: `${Math.min(100, Math.max(3, m.course_mastery_avg))}%` }}
                      />
                    </div>
                  </div>

                  <div className="flex sm:flex-col gap-2 w-[220px] sm:w-[112px]">
                    <button
                      onClick={() => onNavigate('exams', { module_id: m.id })}
                      className="flex-1 py-1.5 px-3 rounded-[4px] bg-[#6B1D2F] hover:bg-[#531523] text-white text-[11px] font-semibold transition cursor-pointer"
                    >
                      Simuler
                    </button>
                    <button
                      onClick={() => onNavigate('courses', { module_id: m.id })}
                      className="flex-1 py-1.5 px-3 rounded-[4px] bg-[#FBF9F5] border border-[#D2C9B8] hover:border-[#9A7438] text-[#161615] text-[11px] font-semibold transition cursor-pointer"
                    >
                      Chapitres
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right 4 Cols: Luxury Velours Grenat Marginalia Folio */}
        <aside className="lg:col-span-4 lg:mt-7 bg-[#241116] border border-[#9A7438] rounded-[6px] p-6 text-[#FBF9F5] space-y-5">
          <div>
            <div className="text-[9.5px] font-bold tracking-[0.16em] uppercase text-[#C7A46B]">
              VEILLE STRATÉGIQUE · SESSION 2025
            </div>
            <h2 className="font-serif-editorial text-[26px] leading-tight font-normal text-[#FBF9F5] mt-2">
              {summary.sn2025_traps} Pièges Marqués « X »
            </h2>
            <p className="text-[12px] text-[#D4C9BA] mt-1.5 leading-relaxed">
              Questions à fort taux d'erreur extraites de vos copies SN.
            </p>
            <button
              onClick={() => onNavigate('exams', { traps_only: true })}
              className="w-full mt-4 py-2.5 px-4 rounded-[5px] bg-[#9A7438] hover:bg-[#AD8340] text-[#19120B] text-xs font-semibold transition cursor-pointer"
            >
              Réviser la sélection Pièges X →
            </button>
          </div>

          <div className="border-t border-[#44252D] pt-4 space-y-3">
            <div className="flex items-center justify-between gap-2">
              <button
                onClick={() => setFolioTab('priority')}
                className={`text-[9.5px] font-bold tracking-[0.14em] uppercase cursor-pointer transition ${
                  folioTab === 'priority' ? 'text-[#C7A46B]' : 'text-[#8F7A70] hover:text-[#D4C9BA]'
                }`}
              >
                CHAPITRES PRIORITAIRES
              </button>
              <button
                onClick={() => setFolioTab('alerts')}
                className={`text-[9.5px] font-bold tracking-[0.14em] uppercase cursor-pointer transition ${
                  folioTab === 'alerts' ? 'text-[#C7A46B]' : 'text-[#8F7A70] hover:text-[#D4C9BA]'
                }`}
              >
                SUPPORTS ({curriculum_alerts?.length || 0})
              </button>
            </div>

            {folioTab === 'priority' ? (
              <div className="divide-y divide-[#391D24]">
                {(due_courses || []).slice(0, 4).map((c, idx) => (
                  <button
                    key={c.id}
                    onClick={() =>
                      onNavigate('courses', { module_id: c.module_id, selected_course_id: c.id })
                    }
                    className="w-full py-3 flex items-center justify-between gap-3 text-left hover:bg-[#2F161D] -mx-2 px-2 rounded-[4px] transition cursor-pointer"
                  >
                    <div className="flex items-baseline gap-3 min-w-0">
                      <span className="font-serif-editorial italic text-[16px] text-[#C7A46B] shrink-0">
                        {String(idx + 1).padStart(2, '0')}
                      </span>
                      <div className="min-w-0">
                        <div className="text-[12.5px] font-semibold text-[#FBF9F5] truncate">
                          {c.canonical_title}
                        </div>
                        <div className="text-[10.5px] text-[#B8A89A] truncate">{c.professor}</div>
                      </div>
                    </div>
                    <span className="font-mono-tabular text-[10.5px] font-semibold text-[#C7A46B] shrink-0">
                      {Math.round(c.mastery_score)}%
                    </span>
                  </button>
                ))}
              </div>
            ) : (
              <div className="space-y-2 max-h-[225px] overflow-y-auto pr-1">
                {(curriculum_alerts || []).map((a) => (
                  <button
                    key={a.id}
                    onClick={() =>
                      onNavigate('courses', { module_id: a.module_id, selected_course_id: a.id })
                    }
                    className="w-full p-2.5 rounded-[4px] bg-[#2C151B] border border-[#44252D] hover:border-[#9A7438] text-left cursor-pointer transition"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[10.5px] text-[#D4C9BA]">{a.professor}</span>
                      <UploadFlagBadge flag={a.upload_flag} />
                    </div>
                    <div className="text-[12px] font-semibold text-[#FBF9F5] mt-1">
                      {a.canonical_title}
                    </div>
                  </button>
                ))}
                {(!curriculum_alerts || curriculum_alerts.length === 0) && (
                  <div className="flex items-center gap-2 text-xs text-[#C7A46B] py-3">
                    <CheckCircle2 className="w-4 h-4" /> Tous les supports 2026–2027 sont complets.
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="flex items-center justify-between pt-2 border-t border-[#391D24] text-[11px]">
            <span className="text-[#C7A46B]">
              Examen Blanc Neuro 2025 : 6 QROC sur 8 tombées en SN.
            </span>
          </div>
        </aside>
      </section>
    </div>
  );
};
