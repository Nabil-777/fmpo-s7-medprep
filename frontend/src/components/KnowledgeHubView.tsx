import React, { useEffect, useState } from 'react';
import { ExternalLink, Image as ImageIcon, Save, Search } from 'lucide-react';
import { api } from '../api';
import type { CourseItem, DriveFileItem, NavTab, QuestionItem } from '../types';
import { ModuleBadge, UploadFlagBadge, VerificationBadge } from './shared';

interface Props {
  initialPreset?: { module_id?: string; high_yield_only?: boolean; selected_course_id?: number } | null;
  onNavigate: (tab: NavTab, preset?: any) => void;
}

export const KnowledgeHubView: React.FC<Props> = ({ initialPreset, onNavigate }) => {
  const [moduleFilter, setModuleFilter] = useState(initialPreset?.module_id || 'all');
  const [flagFilter, setFlagFilter] = useState('all');
  const [highYieldOnly, setHighYieldOnly] = useState(Boolean(initialPreset?.high_yield_only));
  const [search, setSearch] = useState('');
  const [courses, setCourses] = useState<CourseItem[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(
    initialPreset?.selected_course_id || null,
  );
  const [detail, setDetail] = useState<{
    course: CourseItem;
    files: DriveFileItem[];
    questions: QuestionItem[];
    clinical_cases: any[];
  } | null>(null);
  const [notesDraft, setNotesDraft] = useState('');
  const [reviewMsg, setReviewMsg] = useState('');
  const [previewFileId, setPreviewFileId] = useState<string | null>(null);
  const [previewPages, setPreviewPages] = useState<string[]>([]);
  const [previewIdx, setPreviewIdx] = useState(0);
  const [loadingPreview, setLoadingPreview] = useState(false);

  const loadCourses = async () => {
    const res = await api.courses({
      module_id: moduleFilter,
      upload_flag: flagFilter,
      high_yield_only: highYieldOnly,
      q: search,
    });
    setCourses(res.courses);
    if (!selectedId && res.courses.length > 0) {
      setSelectedId(res.courses[0].id);
    }
  };

  useEffect(() => {
    loadCourses();
  }, [moduleFilter, flagFilter, highYieldOnly, search]);

  useEffect(() => {
    if (!selectedId) return;
    setPreviewFileId(null);
    setPreviewPages([]);
    setReviewMsg('');
    api.courseDetail(selectedId).then((res) => {
      setDetail(res);
      setNotesDraft(res.course.notes_markdown || '');
    });
  }, [selectedId]);

  const handleRating = async (rating: string) => {
    if (!detail) return;
    const res = await api.reviewCourse(detail.course.id, rating, notesDraft);
    setReviewMsg(
      `Révision enregistrée · Maîtrise ${res.mastery_score}% · Prochain rappel dans ${res.interval_days} j`,
    );
    const updated = await api.courseDetail(detail.course.id);
    setDetail(updated);
    loadCourses();
  };

  const handleSaveNotes = async () => {
    if (!detail) return;
    await api.reviewCourse(detail.course.id, 'good', notesDraft);
    setReviewMsg('Notes enregistrées et maîtrise actualisée.');
    loadCourses();
  };

  const openVisualPdf = async (fileId: string) => {
    setPreviewFileId(fileId);
    setLoadingPreview(true);
    setPreviewIdx(0);
    try {
      const res = await api.filePages(fileId);
      setPreviewPages(res.pages);
    } catch {
      setPreviewPages([]);
    } finally {
      setLoadingPreview(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Top Filter Line (Board 05) */}
      <div className="bg-white border border-[#E5DFD3] rounded-[5px] p-3 flex flex-wrap items-center gap-2.5">
        <div className="relative flex-1 min-w-[230px]">
          <Search className="w-3.5 h-3.5 text-[#8C857A] absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Rechercher un cours, un professeur…"
            className="w-full pl-9 pr-3 py-1.5 text-xs rounded-[4px] border border-[#D2C9B8] bg-[#FBF9F5] focus:bg-white text-[#161615] placeholder:text-[#6F6A61] focus:outline-none focus:border-[#6B1D2F]"
          />
        </div>

        <select
          value={moduleFilter}
          onChange={(e) => setModuleFilter(e.target.value)}
          className="px-3 py-1.5 text-[11px] font-semibold rounded-[4px] border border-[#D2C9B8] bg-[#F3EFE7] text-[#161615]"
        >
          <option value="all">Tous modules ({courses.length})</option>
          <option value="anapath">Anapath APS</option>
          <option value="endocrino-dermato">Endocrino · Dermato</option>
          <option value="hemato-onco">Hémato · Onco</option>
          <option value="neuro-neurochir">Neuro · NeuroChir</option>
        </select>

        <select
          value={flagFilter}
          onChange={(e) => setFlagFilter(e.target.value)}
          className="px-3 py-1.5 text-[11px] font-semibold rounded-[4px] border border-[#D2C9B8] bg-[#FBF9F5] text-[#6B1D2F]"
        >
          <option value="all">Tous statuts 2026</option>
          <option value="updated_2026">MAJ 2026–2027</option>
          <option value="nv_support_missing">Nv support attendu</option>
          <option value="sans_support">Sans support officiel</option>
        </select>

        <button
          onClick={() => setHighYieldOnly((v) => !v)}
          className={`px-3.5 py-1.5 rounded-[4px] text-[11px] font-semibold border transition cursor-pointer ${
            highYieldOnly
              ? 'bg-[#6B1D2F] text-white border-[#6B1D2F]'
              : 'bg-[#FBF9F5] text-[#161615] border-[#D2C9B8] hover:border-[#9A7438]'
          }`}
        >
          Haute fréquence
        </button>
      </div>

      {/* Master-Detail Split */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Left Sommaire Column */}
        <aside className="lg:col-span-4 bg-white border border-[#E5DFD3] rounded-[5px] p-4 space-y-3">
          <div className="text-[9.5px] font-bold tracking-[0.14em] uppercase text-[#9A7438] px-1">
            SOMMAIRE S7 · {courses.length} CHAPITRES
          </div>

          <div className="space-y-2.5 max-h-[75vh] overflow-y-auto pr-1">
            {courses.map((c, idx) => {
              const active = c.id === selectedId;
              return (
                <button
                  key={c.id}
                  onClick={() => setSelectedId(c.id)}
                  className={`w-full text-left p-3.5 rounded-[4px] border transition cursor-pointer ${
                    active
                      ? 'bg-[#FBF5EE] border-[#9A7438] border-l-4 border-l-[#6B1D2F]'
                      : 'bg-[#FBF9F5] border-[#E5DFD3] hover:border-[#D2C9B8]'
                  }`}
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <div className="flex items-baseline gap-2.5 min-w-0">
                      <span className="font-serif-editorial italic text-[15px] text-[#9A7438] shrink-0">
                        {String(idx + 1).padStart(2, '0')}
                      </span>
                      <span className="text-[13px] font-bold text-[#161615] truncate">
                        {c.canonical_title}
                      </span>
                    </div>
                    <span
                      className={`font-mono-tabular text-[10.5px] font-bold shrink-0 ${
                        active ? 'text-[#6B1D2F]' : 'text-[#6F6A61]'
                      }`}
                    >
                      {Math.round(c.mastery_score)}%
                    </span>
                  </div>

                  <div className="text-[11px] text-[#6F6A61] mt-1 pl-6 truncate">
                    {c.sub_discipline} · {c.professor}
                    {c.question_count ? ` · ${c.question_count} Q` : ''}
                  </div>

                  {c.upload_flag && c.upload_flag !== 'ok' && (
                    <div className="mt-1.5 pl-6">
                      <UploadFlagBadge flag={c.upload_flag} />
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </aside>

        {/* Right Folio Reader */}
        <section className="lg:col-span-8">
          {!detail ? (
            <div className="bg-white border border-[#E5DFD3] rounded-[5px] p-12 text-center text-sm text-[#6F6A61]">
              Sélectionnez un chapitre à gauche pour ouvrir sa fiche complète, ses supports officiels
              et ses résumés visuels Mohamed Jourhi.
            </div>
          ) : (
            <div className="bg-white border border-[#E5DFD3] rounded-[5px] p-6 md:p-7 space-y-5">
              {/* Top Meta + Quiet SRS Bar */}
              <div className="flex flex-wrap items-start justify-between gap-4 pb-4 border-b border-[#E5DFD3]">
                <div className="space-y-2">
                  <div className="text-[9.5px] font-bold tracking-[0.14em] uppercase text-[#9A7438]">
                    {detail.course.sub_discipline.toUpperCase()} · {detail.course.professor.toUpperCase()} ·{' '}
                    {detail.course.promo_status.toUpperCase()}
                  </div>
                  <h2 className="font-serif-editorial text-[26px] leading-snug font-normal text-[#161615]">
                    {detail.course.canonical_title}
                  </h2>
                  <div className="flex flex-wrap items-center gap-2 pt-0.5">
                    <ModuleBadge
                      moduleId={detail.course.module_id}
                      sub={detail.course.sub_discipline}
                    />
                    <UploadFlagBadge flag={detail.course.upload_flag} />
                    <span className="font-mono-tabular text-[11px] font-semibold text-[#6B1D2F]">
                      Maîtrise {Math.round(detail.course.mastery_score)}%
                    </span>
                  </div>
                </div>

                {/* Quiet SRS Bar */}
                <div className="flex items-center gap-1.5 shrink-0">
                  {[
                    { k: 'again', label: '1 j', cls: 'bg-[#FBF9F5] text-[#9E2A2B] border-[#DFC0C0] hover:bg-[#FAF0F0]' },
                    { k: 'hard', label: '2 j', cls: 'bg-[#FBF9F5] text-[#9A7438] border-[#D2C9B8] hover:bg-[#FBF5EE]' },
                    { k: 'good', label: '4 j+', cls: 'bg-[#FBF9F5] text-[#161615] border-[#D2C9B8] hover:bg-[#F3EFE7]' },
                    { k: 'easy', label: 'Acquis', cls: 'bg-[#EFF5F2] text-[#2A5C48] border-[#2A5C48] hover:bg-[#E1ECE6]' },
                  ].map((b) => (
                    <button
                      key={b.k}
                      onClick={() => handleRating(b.k)}
                      className={`px-3 py-1 rounded-[3px] text-[10.5px] font-semibold border transition cursor-pointer ${b.cls}`}
                    >
                      {b.label}
                    </button>
                  ))}
                </div>
              </div>

              {reviewMsg && (
                <div className="px-3.5 py-2 rounded-[4px] bg-[#EFF5F2] border border-[#B8D4C8] text-[#2A5C48] text-xs font-medium">
                  {reviewMsg}
                </div>
              )}

              {/* Travertine Editorial Pearl Digest */}
              {detail.course.high_yield_points && detail.course.high_yield_points.length > 0 && (
                <div className="bg-[#F3EFE7] border border-[#D2C9B8] rounded-[4px] p-4 space-y-2">
                  <div className="text-[9.5px] font-bold tracking-[0.12em] uppercase text-[#6B1D2F]">
                    SYNTHÈSE HAUT RENDEMENT EXTRAITE DU SUPPORT
                  </div>
                  <ul className="space-y-1.5 text-[12px] text-[#161615] leading-relaxed list-disc pl-4">
                    {detail.course.high_yield_points.map((pt, i) => (
                      <li key={i}>{pt}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Clean File Tabs (Official Course vs Mohamed Jourhi Visual Sheet) */}
              <div className="space-y-2.5">
                <div className="text-[9.5px] font-bold tracking-[0.12em] uppercase text-[#6F6A61]">
                  SUPPORTS DRIVE & FICHES VISUELLES ({detail.files.length})
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {detail.files.map((f) => {
                    const isPreviewing = previewFileId === f.id;
                    return (
                      <div
                        key={f.id}
                        className={`p-3.5 rounded-[4px] border flex flex-col justify-between gap-2.5 transition ${
                          isPreviewing
                            ? 'bg-[#241116] border-[#9A7438] text-[#FBF9F5]'
                            : 'bg-[#FBF9F5] border-[#D2C9B8] text-[#161615]'
                        }`}
                      >
                        <div>
                          <div className="flex items-center justify-between gap-2">
                            <span
                              className={`text-[9.5px] font-bold tracking-[0.1em] uppercase ${
                                isPreviewing ? 'text-[#C7A46B]' : 'text-[#6F6A61]'
                              }`}
                            >
                              {f.category === 'resume_mohamed'
                                ? 'Fiche Visuelle Mohamed Jourhi'
                                : 'Support Officiel'}
                            </span>
                            {f.version_tag && (
                              <span
                                className={`font-mono-tabular text-[10px] font-semibold px-1.5 py-0.5 rounded-[3px] ${
                                  isPreviewing
                                    ? 'bg-[#391D24] text-[#C7A46B]'
                                    : 'bg-white border border-[#D2C9B8] text-[#9A7438]'
                                }`}
                              >
                                {f.version_tag}
                              </span>
                            )}
                          </div>
                          <div className="text-[12px] font-semibold mt-1 break-words">{f.name}</div>
                          <div
                            className={`font-mono-tabular text-[10.5px] mt-0.5 ${
                              isPreviewing ? 'text-[#D4C9BA]' : 'text-[#6F6A61]'
                            }`}
                          >
                            {(f.size / 1e6).toFixed(1)} Mo ·{' '}
                            {f.page_count ? `${f.page_count} p.` : 'Support'}
                            {f.is_scanned ? ' · Visuel' : ''}
                          </div>
                        </div>

                        <div className="flex items-center gap-2">
                          {f.name.toLowerCase().endsWith('.pdf') && (
                            <button
                              onClick={() => openVisualPdf(f.id)}
                              className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-[3px] text-[11px] font-semibold border transition cursor-pointer ${
                                isPreviewing
                                  ? 'bg-[#9A7438] border-[#9A7438] text-[#19120B]'
                                  : 'bg-white border-[#D2C9B8] hover:border-[#6B1D2F] text-[#161615]'
                              }`}
                            >
                              <ImageIcon className="w-3 h-3" /> Feuilleter ici
                            </button>
                          )}
                          <a
                            href={`/api/files/${f.id}/view`}
                            target="_blank"
                            rel="noreferrer"
                            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-[3px] text-[11px] font-semibold transition ${
                              isPreviewing
                                ? 'bg-[#391D24] text-[#FBF9F5] hover:bg-[#4E2832]'
                                : 'bg-[#6B1D2F] text-white hover:bg-[#531523]'
                            }`}
                          >
                            <ExternalLink className="w-3 h-3" /> Ouvrir
                          </a>
                        </div>
                      </div>
                    );
                  })}
                  {detail.files.length === 0 && (
                    <div className="sm:col-span-2 p-4 rounded-[4px] bg-[#FBF9F5] border border-dashed border-[#D2C9B8] text-xs text-[#6F6A61]">
                      Aucun support PDF direct détecté pour ce chapitre (« sans support ») —
                      révisez directement via les questions d'annales liées ci-dessous.
                    </div>
                  )}
                </div>
              </div>

              {/* Darkroom High-Contrast Slide Viewport */}
              {previewFileId && (
                <div className="rounded-[4px] bg-[#191715] border border-[#2F2B26] p-4 text-[#FBF9F5] space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-mono-tabular text-[10.5px] font-semibold text-[#C7A46B]">
                      VISIONNEUSE{' '}
                      {previewPages.length
                        ? `· PAGE ${String(previewIdx + 1).padStart(2, '0')} / ${String(previewPages.length).padStart(2, '0')}`
                        : ''}
                    </span>

                    <div className="flex items-center gap-2">
                      <button
                        disabled={previewIdx <= 0}
                        onClick={() => setPreviewIdx((i) => Math.max(0, i - 1))}
                        className="px-2.5 py-1 rounded-[3px] bg-[#292521] border border-[#4A433B] text-[#E5DFD3] text-[10.5px] font-semibold disabled:opacity-35 cursor-pointer"
                      >
                        ← Préc.
                      </button>
                      <button
                        disabled={previewIdx >= previewPages.length - 1}
                        onClick={() =>
                          setPreviewIdx((i) => Math.min(previewPages.length - 1, i + 1))
                        }
                        className="px-2.5 py-1 rounded-[3px] bg-[#9A7438] text-[#19120B] text-[10.5px] font-semibold disabled:opacity-35 cursor-pointer"
                      >
                        Suiv. →
                      </button>
                      <button
                        onClick={() => setPreviewFileId(null)}
                        className="px-2.5 py-1 rounded-[3px] bg-[#292521] border border-[#4A433B] text-[#D4C9BA] text-[10.5px] cursor-pointer"
                      >
                        Fermer
                      </button>
                    </div>
                  </div>

                  {loadingPreview ? (
                    <div className="py-16 text-center text-xs text-[#D4C9BA]">
                      Rendu des pages HD en cours…
                    </div>
                  ) : previewPages[previewIdx] ? (
                    <div className="bg-white rounded-[2px] p-1">
                      <img
                        src={previewPages[previewIdx]}
                        alt={`Page ${previewIdx + 1}`}
                        className="w-full max-h-[600px] object-contain"
                      />
                    </div>
                  ) : (
                    <div className="py-8 text-center text-xs text-[#E5B8B8]">
                      Impossible de rendre ce document.
                    </div>
                  )}
                </div>
              )}

              {/* Notes Editor */}
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[9.5px] font-bold tracking-[0.12em] uppercase text-[#6F6A61]">
                    SYNTHÈSE & NOTES PERSONNELLES DE COURS
                  </span>
                  <button
                    onClick={handleSaveNotes}
                    className="inline-flex items-center gap-1.5 px-3 py-1 rounded-[4px] bg-[#6B1D2F] hover:bg-[#531523] text-white text-[11px] font-semibold cursor-pointer transition"
                  >
                    <Save className="w-3 h-3" /> Sauvegarder mes notes
                  </button>
                </div>
                <textarea
                  value={notesDraft}
                  onChange={(e) => setNotesDraft(e.target.value)}
                  rows={6}
                  placeholder="Ajoutez vos moyens mnémotechniques, pièges du professeur ou notes personnelles…"
                  className="w-full rounded-[4px] border border-[#D2C9B8] bg-[#FBF9F5] focus:bg-white focus:border-[#6B1D2F] p-3 font-mono-tabular text-[11.5px] text-[#161615] focus:outline-none"
                />
              </div>

              {/* Linked Clinical Cases & Questions */}
              <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-[#E5DFD3]">
                <span className="font-mono-tabular text-[11px] text-[#6F6A61]">
                  {detail.questions.length} questions indexées
                  {detail.clinical_cases.length > 0 &&
                    ` · ${detail.clinical_cases.length} cas clinique(s)`}
                </span>

                <div className="flex flex-wrap gap-2">
                  {detail.clinical_cases.length > 0 && (
                    <button
                      onClick={() => onNavigate('clinical', { slug: detail.clinical_cases[0].slug })}
                      className="px-3.5 py-1.5 rounded-[4px] bg-[#F3EFE7] border border-[#D2C9B8] hover:border-[#9A7438] text-[#161615] text-[11px] font-semibold cursor-pointer"
                    >
                      Ouvrir le Cas Clinique →
                    </button>
                  )}
                  <button
                    onClick={() => onNavigate('exams', { course_id: detail.course.id })}
                    className="px-3.5 py-1.5 rounded-[4px] bg-[#6B1D2F] hover:bg-[#531523] text-white text-[11px] font-semibold cursor-pointer"
                  >
                    S'entraîner sur ce cours ({detail.questions.length} Q) →
                  </button>
                </div>
              </div>

              {detail.questions.slice(0, 3).length > 0 && (
                <div className="space-y-2 pt-1">
                  <div className="text-[9.5px] font-bold tracking-[0.12em] uppercase text-[#6F6A61]">
                    APERÇU DES ANNALES RATTACHÉES
                  </div>
                  {detail.questions.slice(0, 3).map((q) => (
                    <div
                      key={q.id}
                      className="p-3 rounded-[4px] border border-[#E5DFD3] bg-[#FBF9F5] text-xs space-y-1"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono-tabular text-[10.5px] font-semibold text-[#9A7438]">
                          {q.source_label}
                        </span>
                        <VerificationBadge status={q.verification_status} />
                      </div>
                      <div className="text-[12.5px] text-[#161615]">{q.stem}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
};
