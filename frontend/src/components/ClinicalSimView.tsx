import React, { useEffect, useState } from 'react';
import { api } from '../api';
import type { ClinicalCaseItem, NavTab } from '../types';
import { ClinicalCasePlayer } from './ClinicalCasePlayer';
import { ModuleBadge } from './shared';

interface Props {
  initialPreset?: { module_id?: string; slug?: string } | null;
  onNavigate: (tab: NavTab, preset?: any) => void;
}

export const ClinicalSimView: React.FC<Props> = ({ initialPreset, onNavigate }) => {
  const [moduleFilter, setModuleFilter] = useState(initialPreset?.module_id || 'all');
  const [cases, setCases] = useState<ClinicalCaseItem[]>([]);
  const [activeCase, setActiveCase] = useState<ClinicalCaseItem | null>(null);

  const loadList = async () => {
    const res = await api.clinicalCases(moduleFilter);
    setCases(res.cases);
    if (initialPreset?.slug && !activeCase) {
      const target = res.cases.find((c: ClinicalCaseItem) => c.slug === initialPreset.slug);
      if (target) setActiveCase(target);
    }
  };

  useEffect(() => {
    loadList();
  }, [moduleFilter]);

  if (activeCase) {
    return (
      <ClinicalCasePlayer
        key={activeCase.id}
        activeCase={activeCase}
        backLabel="Toutes les situations cliniques"
        onBack={() => setActiveCase(null)}
        onAttemptRecorded={loadList}
        onNavigate={onNavigate}
      />
    );
  }

  return (
    <div className="space-y-5">
      <div className="bg-white border border-[#E5DFD3] rounded-[5px] p-5 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="text-[9.5px] font-bold tracking-[0.14em] uppercase text-[#9A7438]">
            GRAND ROUNDS · {cases.length} DOSSIERS PROGRESSIFS S7
          </div>
          <h2 className="font-serif-editorial text-[24px] font-normal text-[#161615] mt-1">
            Situations Cliniques & Urgences FMPO
          </h2>
        </div>
        <select
          value={moduleFilter}
          onChange={(e) => setModuleFilter(e.target.value)}
          className="px-3.5 py-2 text-xs font-medium rounded-[4px] border border-[#D2C9B8] bg-[#FBF9F5] text-[#161615]"
        >
          <option value="all">Tous les modules</option>
          <option value="neuro-neurochir">Neuro · NeuroChir</option>
          <option value="endocrino-dermato">Endocrino · Dermato</option>
          <option value="hemato-onco">Hémato · Onco</option>
          <option value="anapath">Anapath APS</option>
        </select>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {cases.map((c) => (
          <div
            key={c.id}
            className="bg-white border border-[#E5DFD3] hover:border-[#D2C9B8] rounded-[5px] p-6 flex flex-col justify-between gap-4 transition"
          >
            <div className="space-y-2.5">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <ModuleBadge moduleId={c.module_id} sub={c.sub_discipline} />
                <span className="font-mono-tabular text-[10.5px] font-semibold text-[#6F6A61]">
                  {c.steps_json.length} étapes · {c.difficulty}
                </span>
              </div>
              <h3 className="font-serif-editorial text-[20px] leading-snug text-[#161615] font-normal">
                {c.title}
              </h3>
              <p className="text-[12.5px] text-[#6F6A61] line-clamp-3 leading-relaxed">
                {c.patient_summary}
              </p>
              <div className="font-mono-tabular text-[10.5px] text-[#9A7438] font-medium">
                Source : {c.source_tag}
              </div>
            </div>

            <div className="flex items-center justify-between pt-3 border-t border-[#E5DFD3]">
              <div className="font-mono-tabular text-[11px] text-[#6F6A61]">
                {c.best_ratio !== null && c.best_ratio !== undefined
                  ? `Meilleur score : ${Math.round(c.best_ratio * 100)}% (${c.attempt_count} essai)`
                  : 'Dossier non débuté'}
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
    </div>
  );
};
