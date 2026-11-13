import React, { useEffect, useState } from 'react';
import { ArrowRight, BookOpen, Play, Search, X } from 'lucide-react';
import { api } from './api';
import { ClinicalSimView } from './components/ClinicalSimView';
import { DashboardView } from './components/DashboardView';
import { ExamSimulatorView } from './components/ExamSimulatorView';
import { KnowledgeHubView } from './components/KnowledgeHubView';
import { ScanDigitizerView } from './components/ScanDigitizerView';
import { StrikeRadarView } from './components/StrikeRadarView';
import { ModuleBadge } from './components/shared';
import type { CourseItem, NavTab } from './types';

const NAV_ITEMS: { id: NavTab; label: string }[] = [
  { id: 'dashboard', label: "Vue d'ensemble" },
  { id: 'courses', label: 'Cours & Fiches' },
  { id: 'clinical', label: 'Clinique' },
  { id: 'exams', label: 'Examens' },
  { id: 'radar', label: 'Radar' },
  { id: 'scans', label: 'Scans' },
];

export default function App() {
  const [tab, setTab] = useState<NavTab>('dashboard');
  const [preset, setPreset] = useState<any>(null);
  const [presetKey, setPresetKey] = useState(0);
  const [dashboard, setDashboard] = useState<any>(null);

  // Command palette (⌘K) state
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<CourseItem[]>([]);

  const loadDash = () => {
    api.dashboard().then(setDashboard).catch(() => {});
  };

  useEffect(() => {
    loadDash();
  }, [tab]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setSearchOpen((v) => !v);
      } else if (e.key === 'Escape') {
        setSearchOpen(false);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  useEffect(() => {
    if (!searchOpen) return;
    const t = setTimeout(() => {
      api
        .courses(searchQuery ? { q: searchQuery } : { high_yield_only: true })
        .then((res) => setSearchResults((res.courses || []).slice(0, 8)))
        .catch(() => setSearchResults([]));
    }, 120);
    return () => clearTimeout(t);
  }, [searchOpen, searchQuery]);

  const navigate = (nextTab: NavTab, nextPreset?: any) => {
    setPreset(nextPreset || null);
    setPresetKey((k) => k + 1);
    setTab(nextTab);
    setSearchOpen(false);
  };

  const readyCount = dashboard?.summary?.ready_questions ?? 1044;

  return (
    <div className="min-h-screen flex flex-col bg-[#FBF9F5] text-[#161615]">
      {/* Top Editorial Masthead (Figma Boards 02–06) */}
      <header className="sticky top-0 z-30 bg-white border-b border-[#E5DFD3]">
        <div className="max-w-[1440px] mx-auto px-4 sm:px-8 lg:px-14 h-[70px] flex items-center justify-between gap-4">
          {/* Crest & Wordmark */}
          <button
            onClick={() => navigate('dashboard')}
            className="flex items-center gap-3 text-left shrink-0 cursor-pointer group"
          >
            <div className="w-[34px] h-[34px] rounded-[4px] bg-[#241116] border border-[#9A7438] flex items-center justify-center shrink-0">
              <span className="font-serif-editorial italic font-bold text-[18px] leading-none text-[#F5ECD8]">
                M
              </span>
            </div>
            <div>
              <div className="font-serif-editorial text-[19px] leading-none tracking-tight text-[#161615]">
                <span className="font-bold">MedPrep </span>
                <span className="italic font-normal text-[#9A7438]">S7</span>
              </div>
              <div className="text-[8.5px] font-semibold tracking-[0.14em] uppercase text-[#9B9488] mt-1">
                FMPO OUJDA · QUATRIÈME ANNÉE
              </div>
            </div>
          </button>

          {/* Center Navigation */}
          <nav className="flex items-center gap-5 sm:gap-7 overflow-x-auto h-full no-scrollbar">
            {NAV_ITEMS.map((item) => {
              const active = tab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => navigate(item.id)}
                  className={`relative h-full inline-flex items-center text-[12.5px] whitespace-nowrap transition-colors cursor-pointer ${
                    active
                      ? 'font-bold text-[#6B1D2F]'
                      : 'font-medium text-[#6F6A61] hover:text-[#161615]'
                  }`}
                >
                  <span>{item.label}</span>
                  {active && (
                    <span className="absolute bottom-0 inset-x-0 h-[2.5px] bg-[#6B1D2F]" />
                  )}
                </button>
              );
            })}
          </nav>

          {/* Right Search Trigger + Tabular Corpus Status */}
          <div className="hidden md:flex items-center gap-4 shrink-0">
            <button
              onClick={() => {
                setSearchQuery('');
                setSearchOpen(true);
              }}
              className="w-[184px] h-[32px] px-2.5 rounded-[5px] bg-[#FBF9F5] border border-[#E5DFD3] hover:border-[#D2C9B8] flex items-center justify-between text-[11px] text-[#6F6A61] cursor-pointer transition"
            >
              <span className="flex items-center gap-2">
                <Search className="w-3.5 h-3.5 text-[#8C857A]" />
                <span>Rechercher…</span>
              </span>
              <span className="font-mono-tabular text-[10px] font-semibold text-[#9B9488]">⌘K</span>
            </button>
            <div className="h-6 w-[1px] bg-[#E5DFD3]" />
            <div className="font-mono-tabular text-[11px] font-semibold text-[#6F6A61]">
              {Number(readyCount).toLocaleString('fr-FR')} Q · SN25
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-[1440px] w-full mx-auto px-4 sm:px-8 lg:px-14 py-7">
        {tab === 'dashboard' && <DashboardView data={dashboard} onNavigate={navigate} />}
        {tab === 'courses' && (
          <KnowledgeHubView key={`c-${presetKey}`} initialPreset={preset} onNavigate={navigate} />
        )}
        {tab === 'clinical' && (
          <ClinicalSimView key={`cl-${presetKey}`} initialPreset={preset} onNavigate={navigate} />
        )}
        {tab === 'exams' && (
          <ExamSimulatorView key={`ex-${presetKey}`} initialPreset={preset} />
        )}
        {tab === 'radar' && <StrikeRadarView onNavigate={navigate} />}
        {tab === 'scans' && <ScanDigitizerView />}
      </main>

      {/* Quick Search Palette (⌘K) */}
      {searchOpen && (
        <div
          className="fixed inset-0 z-50 bg-[#191715]/50 backdrop-blur-[1px] flex items-start justify-center pt-20 px-4"
          onClick={() => setSearchOpen(false)}
        >
          <div
            className="w-full max-w-xl bg-white border border-[#D2C9B8] rounded-[6px] shadow-xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-3 px-4 py-3 border-b border-[#E5DFD3] bg-[#FBF9F5]">
              <Search className="w-4 h-4 text-[#9A7438]" />
              <input
                autoFocus
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Rechercher un cours, un professeur (Mabrouk, Zerrouki, Bennani…)"
                className="flex-1 bg-transparent text-sm text-[#161615] placeholder:text-[#9B9488] focus:outline-none"
              />
              <button
                onClick={() => setSearchOpen(false)}
                className="p-1 text-[#6F6A61] hover:text-[#161615] cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="divide-y divide-[#E5DFD3] max-h-80 overflow-y-auto">
              {searchResults.map((c) => (
                <button
                  key={c.id}
                  onClick={() =>
                    navigate('courses', { module_id: c.module_id, selected_course_id: c.id })
                  }
                  className="w-full px-4 py-3 text-left hover:bg-[#FBF9F5] flex items-center justify-between gap-3 cursor-pointer"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <ModuleBadge moduleId={c.module_id} sub={c.sub_discipline} />
                      <span className="text-[11px] text-[#6F6A61]">{c.professor}</span>
                    </div>
                    <div className="text-sm font-semibold text-[#161615] truncate flex items-center gap-1.5">
                      <BookOpen className="w-3.5 h-3.5 text-[#9A7438] shrink-0" />
                      <span>{c.canonical_title}</span>
                    </div>
                  </div>
                  <ArrowRight className="w-4 h-4 text-[#6F6A61] shrink-0" />
                </button>
              ))}
              {searchResults.length === 0 && (
                <div className="p-6 text-center text-xs text-[#6F6A61]">
                  Aucun chapitre correspondant trouvé.
                </div>
              )}
            </div>
            <div className="px-4 py-2.5 bg-[#F3EFE7] border-t border-[#E5DFD3] flex flex-wrap items-center justify-between gap-2 text-[11px] text-[#6F6A61]">
              <span>Raccourcis session normale :</span>
              <div className="flex gap-2">
                <button
                  onClick={() => navigate('exams', { source_label: 'EXAMEN APS 2025 SN' })}
                  className="inline-flex items-center gap-1 px-2 py-0.5 bg-white border border-[#D2C9B8] rounded-[4px] font-semibold text-[#161615] hover:border-[#6B1D2F] cursor-pointer"
                >
                  <Play className="w-3 h-3 text-[#6B1D2F]" /> APS 2025
                </button>
                <button
                  onClick={() => navigate('exams', { traps_only: true })}
                  className="px-2 py-0.5 bg-[#FAF0F0] border border-[#E5B8B8] rounded-[4px] font-semibold text-[#9E2A2B] cursor-pointer"
                >
                  Pièges X 2025
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
