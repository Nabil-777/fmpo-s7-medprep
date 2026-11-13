import React from 'react';

export const MODULE_ORDER = ['anapath', 'endocrino-dermato', 'hemato-onco', 'neuro-neurochir'] as const;

export const MODULE_ROMAN: Record<string, string> = {
  anapath: 'I.',
  'endocrino-dermato': 'II.',
  'hemato-onco': 'III.',
  'neuro-neurochir': 'IV.',
};

export const MODULE_META: Record<string, { label: string; short: string }> = {
  'neuro-neurochir': {
    label: 'Neuro · NeuroChir',
    short: 'Neuro',
  },
  'endocrino-dermato': {
    label: 'Endocrino · Dermato',
    short: 'Endo-Derm',
  },
  'hemato-onco': {
    label: 'Hémato · Onco',
    short: 'Hémato',
  },
  anapath: {
    label: 'Anapath APS',
    short: 'APS',
  },
};

export function sortModulesEditorial<T extends { id: string }>(modules: T[]): T[] {
  const rank = (id: string) => {
    const idx = MODULE_ORDER.indexOf(id as (typeof MODULE_ORDER)[number]);
    return idx === -1 ? 99 : idx;
  };
  return [...modules].sort((a, b) => rank(a.id) - rank(b.id));
}

export function ModuleBadge({ moduleId, sub }: { moduleId: string; sub?: string }) {
  const m = MODULE_META[moduleId] || { label: moduleId, short: moduleId };
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-[4px] text-[11px] font-semibold bg-[#FBF9F5] text-[#161615] border border-[#D2C9B8] whitespace-nowrap">
      <span>{m.label}</span>
      {sub ? <span className="text-[#6F6A61] font-medium">· {sub}</span> : null}
    </span>
  );
}

export function UploadFlagBadge({ flag }: { flag: string }) {
  if (flag === 'nv_support_missing') {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-[4px] text-[10.5px] font-semibold bg-[#FAF0F0] text-[#9E2A2B] border border-[#E5B8B8] whitespace-nowrap">
        Nv support attendu
      </span>
    );
  }
  if (flag === 'sans_support') {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-[4px] text-[10.5px] font-semibold bg-[#F3EFE7] text-[#6F6A61] border border-[#D2C9B8] whitespace-nowrap">
        Sans support officiel
      </span>
    );
  }
  if (flag === 'updated_2026') {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-[4px] text-[10.5px] font-semibold bg-[#FBF5EE] text-[#9A7438] border border-[#DFC9A6] whitespace-nowrap">
        MAJ 2026–2027
      </span>
    );
  }
  return null;
}

export function VerificationBadge({ status }: { status: string }) {
  if (status === 'student_mistake_flagged') {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-[4px] text-[10.5px] font-semibold bg-[#FAF0F0] text-[#9E2A2B] border border-[#E5B8B8] whitespace-nowrap">
        Piège 2025 X
      </span>
    );
  }
  if (status === 'verified_key') {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-[4px] text-[10.5px] font-semibold bg-[#EFF5F2] text-[#2A5C48] border border-[#B8D4C8] whitespace-nowrap">
        Clé vérifiée
      </span>
    );
  }
  if (status === 'corrigé_raster' || status === 'ai_verified') {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-[4px] text-[10.5px] font-semibold bg-[#FBF5EE] text-[#9A7438] border border-[#DFC9A6] whitespace-nowrap">
        {status === 'corrigé_raster' ? 'Corrigé annoté' : 'Vérifié IA / Cours'}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center px-2.5 py-0.5 rounded-[4px] text-[10.5px] font-semibold bg-[#F3EFE7] text-[#6F6A61] border border-[#D2C9B8] whitespace-nowrap">
      Entraînement libre
    </span>
  );
}
