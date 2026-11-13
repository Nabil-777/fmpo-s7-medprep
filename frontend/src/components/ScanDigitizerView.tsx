import React, { useEffect, useState } from 'react';
import { CheckCircle2, Loader2, Save, Sparkles, Upload } from 'lucide-react';
import { api } from '../api';
import { ModuleBadge, VerificationBadge } from './shared';

export const ScanDigitizerView: React.FC = () => {
  const [catalog, setCatalog] = useState<any>(null);
  const [mode, setMode] = useState<'sn2025' | 'drive' | 'upload'>('sn2025');
  const [selectedPrefix, setSelectedPrefix] = useState('aps');
  const [snPages, setSnPages] = useState<any[]>([]);
  const [pageIdx, setPageIdx] = useState(0);

  const [activeJob, setActiveJob] = useState<{
    job_id: string;
    filename: string;
    module_id: string;
    pages: any[];
  } | null>(null);
  const [jobPageIdx, setJobPageIdx] = useState(0);
  const [ocrDrafts, setOcrDrafts] = useState<any[]>([]);
  const [ocrBusy, setOcrBusy] = useState(false);
  const [preparingId, setPreparingId] = useState<string | null>(null);
  const [saveFeedback, setSaveFeedback] = useState('');

  const [uploadModule, setUploadModule] = useState('anapath');
  const [uploadType] = useState('examen');

  useEffect(() => {
    api.scanCatalog().then(setCatalog);
  }, []);

  useEffect(() => {
    if (mode !== 'sn2025') return;
    api.sn2025Batch(selectedPrefix).then((res) => {
      setSnPages(res.pages);
      setPageIdx(0);
      setSaveFeedback('');
    });
  }, [mode, selectedPrefix]);

  const handlePrepareDriveScan = async (fileId: string, modId: string) => {
    setPreparingId(fileId);
    setSaveFeedback('');
    try {
      const res = await api.prepareDriveScan(fileId);
      setActiveJob({ ...res, module_id: modId || 'anapath' });
      setJobPageIdx(0);
      setOcrDrafts([]);
      setMode('drive');
    } catch (e: any) {
      setSaveFeedback(`Erreur préparation : ${e.message}`);
    } finally {
      setPreparingId(null);
    }
  };

  const handleUploadFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append('file', file);
    fd.append('module_id', uploadModule);
    fd.append('source_type', uploadType);
    setOcrBusy(true);
    setSaveFeedback('');
    try {
      const res = await api.uploadScan(fd);
      setActiveJob(res);
      setJobPageIdx(0);
      setOcrDrafts([]);
      setMode('drive');
    } catch (err: any) {
      setSaveFeedback(`Erreur import : ${err.message}`);
    } finally {
      setOcrBusy(false);
    }
  };

  const handleRunOcr = async () => {
    if (!activeJob) return;
    setOcrBusy(true);
    setSaveFeedback('');
    try {
      const res = await api.ocrJobPage(
        activeJob.job_id,
        jobPageIdx + 1,
        `${activeJob.filename} (${activeJob.module_id})`,
      );
      setOcrDrafts(res.ocr?.questions || []);
    } catch (err: any) {
      setSaveFeedback(`Erreur OCR Vision : ${err.message}`);
    } finally {
      setOcrBusy(false);
    }
  };

  const saveSnQuestionEdit = async (q: any, newAnswersRaw: string, newExpl: string) => {
    const letters = newAnswersRaw
      .toUpperCase()
      .split(/[\s,;]+/)
      .filter(Boolean);
    await api.saveQuestion({
      question_id: q.id,
      module_id: q.module_id,
      sub_discipline: q.sub_discipline,
      source_label: q.source_label,
      question_number: q.question_number,
      question_type: q.question_type,
      stem: q.stem,
      statements: q.statements_json,
      options: q.options_json,
      correct_answers: letters,
      rubric_points: q.rubric_json?.points || [],
      explanation: newExpl,
      scan_page_image: q.scan_page_image,
      verification_status: 'verified_key',
    });
    setSaveFeedback(`Question #${q.question_number || q.id} vérifiée et mise à jour.`);
    const refreshed = await api.sn2025Batch(selectedPrefix);
    setSnPages(refreshed.pages);
  };

  const saveDraftToQBank = async (draft: any, dIdx: number) => {
    if (!activeJob) return;
    const pageImg = activeJob.pages[jobPageIdx]?.image;
    const corr = draft.verified_correct_letters || draft.marked_letters || [];
    const subMap: Record<string, string> = {
      anapath: 'Anatomopathologie',
      'endocrino-dermato': 'Endocrinologie',
      'hemato-onco': 'Hématologie',
      'neuro-neurochir': 'Neurologie',
    };
    await api.saveQuestion({
      module_id: activeJob.module_id,
      sub_discipline: subMap[activeJob.module_id] || 'Médecine S7',
      source_label: activeJob.filename.replace(/\.pdf$/i, ''),
      question_number: draft.question_number || dIdx + 1,
      question_type: draft.question_type || 'qcm_multi',
      stem: draft.stem,
      statements: draft.statements || [],
      options: draft.options || [],
      correct_answers: Array.isArray(corr) ? corr : [],
      rubric_points: draft.rubric_points || [],
      explanation: draft.explanation || '',
      scan_page_image: pageImg,
      verification_status: 'verified_key',
    });
    setSaveFeedback(`Question extraite « ${(draft.stem || '').slice(0, 40)}… » enregistrée.`);
  };

  const curSnPage = snPages[pageIdx];

  return (
    <div className="space-y-5">
      {/* Studio Header & Mode Switch (Board 06 bottom) */}
      <div className="bg-white border border-[#E5DFD3] rounded-[5px] p-5 flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-1 max-w-2xl">
          <div className="text-[9.5px] font-bold tracking-[0.14em] uppercase text-[#9A7438]">
            STUDIO SCANS & OCR VISION · CONTRÔLE CÔTÉ À CÔTE
          </div>
          <h2 className="font-serif-editorial text-[24px] leading-snug font-normal text-[#161615]">
            Atelier de Numérisation &{' '}
            <span className="italic text-[#6B1D2F]">Vérification des Copies</span>
          </h2>
          <p className="text-[12px] text-[#6F6A61]">
            Inspectez chaque page originale face aux propositions extraites, lancez l'extraction
            OCR Vision sur vos archives Drive ou importez un PDF.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setMode('sn2025')}
            className={`px-3.5 py-2 rounded-[4px] text-[11px] font-semibold border transition cursor-pointer ${
              mode === 'sn2025'
                ? 'bg-[#241116] text-[#FBF9F5] border-[#241116]'
                : 'bg-[#FBF9F5] text-[#161615] border-[#D2C9B8] hover:border-[#9A7438]'
            }`}
          >
            Contrôle 2025 SN (23 pages)
          </button>
          <button
            onClick={() => setMode('drive')}
            className={`px-3.5 py-2 rounded-[4px] text-[11px] font-semibold border transition cursor-pointer ${
              mode === 'drive'
                ? 'bg-[#241116] text-[#FBF9F5] border-[#241116]'
                : 'bg-[#FBF9F5] text-[#161615] border-[#D2C9B8] hover:border-[#9A7438]'
            }`}
          >
            Archives Drive
          </button>
          <label className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-[4px] bg-[#6B1D2F] hover:bg-[#531523] text-white text-[11px] font-semibold cursor-pointer transition">
            <Upload className="w-3.5 h-3.5" /> Importer PDF / Image
            <input type="file" accept=".pdf,image/*" onChange={handleUploadFile} className="hidden" />
          </label>
        </div>
      </div>

      {saveFeedback && (
        <div className="px-4 py-2.5 rounded-[4px] bg-[#EFF5F2] border border-[#B8D4C8] text-[#2A5C48] text-xs font-semibold flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4" />
          <span>{saveFeedback}</span>
        </div>
      )}

      {/* MODE 1: SN 2025 Side-by-side Darkroom Verification */}
      {mode === 'sn2025' && (
        <div className="space-y-4">
          <div className="bg-white border border-[#E5DFD3] rounded-[5px] p-3.5 flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap gap-2">
              {[
                { p: 'aps', l: 'APS 2025 SN (6 p.)' },
                { p: 'endo', l: 'Endocrino 2025 SN (4 p.)' },
                { p: 'derm', l: 'Dermato 2025 SN (6 p.)' },
                { p: 'hemato', l: 'Hémato-Onco 2025 SN (6 p.)' },
                { p: 'neuro', l: 'Neuro-NeuroChir (1 p.)' },
              ].map((b) => (
                <button
                  key={b.p}
                  onClick={() => setSelectedPrefix(b.p)}
                  className={`px-3 py-1.5 rounded-[4px] text-[11px] font-semibold border transition cursor-pointer ${
                    selectedPrefix === b.p
                      ? 'bg-[#6B1D2F] text-white border-[#6B1D2F]'
                      : 'bg-[#FBF9F5] text-[#6F6A61] border-[#D2C9B8] hover:border-[#9A7438]'
                  }`}
                >
                  {b.l}
                </button>
              ))}
            </div>

            {snPages.length > 0 && (
              <div className="flex items-center gap-2 font-mono-tabular text-[11px] font-semibold">
                <button
                  disabled={pageIdx <= 0}
                  onClick={() => setPageIdx((i) => Math.max(0, i - 1))}
                  className="px-2.5 py-1 rounded-[3px] bg-white border border-[#D2C9B8] text-[#161615] disabled:opacity-40 cursor-pointer"
                >
                  ← Page préc.
                </button>
                <span className="text-[#6F6A61]">
                  {String(pageIdx + 1).padStart(2, '0')} / {String(snPages.length).padStart(2, '0')}
                </span>
                <button
                  disabled={pageIdx >= snPages.length - 1}
                  onClick={() => setPageIdx((i) => Math.min(snPages.length - 1, i + 1))}
                  className="px-2.5 py-1 rounded-[3px] bg-white border border-[#D2C9B8] text-[#161615] disabled:opacity-40 cursor-pointer"
                >
                  Page suiv. →
                </button>
              </div>
            )}
          </div>

          {curSnPage && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
              {/* Left Darkroom Scan Sheet */}
              <div className="lg:col-span-6 bg-[#191715] border border-[#2F2B26] rounded-[4px] p-4 space-y-3">
                <div className="font-mono-tabular text-[10px] font-semibold tracking-wider text-[#C7A46B] uppercase">
                  PAGE ORIGINALE : {curSnPage.filename} · {String(pageIdx + 1).padStart(2, '0')} /{' '}
                  {String(snPages.length).padStart(2, '0')}
                </div>
                <div className="bg-[#FBF9F5] p-1.5 rounded-[3px]">
                  <img
                    src={curSnPage.image}
                    alt={curSnPage.filename}
                    className="w-full rounded-[2px] object-contain max-h-[78vh]"
                  />
                </div>
              </div>

              {/* Right Structured Question Inspector */}
              <div className="lg:col-span-6 space-y-3.5 max-h-[84vh] overflow-y-auto pr-1">
                {curSnPage.questions.map((q: any) => (
                  <SnQuestionVerifyCard key={q.id} q={q} onSave={saveSnQuestionEdit} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* MODE 2: Drive Scanned PDFs & OCR Vision */}
      {mode === 'drive' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
          <div className="lg:col-span-4 bg-white border border-[#E5DFD3] rounded-[5px] p-4 space-y-3">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-[11px] font-bold uppercase tracking-[0.1em] text-[#6F6A61]">
                Archives scannées Drive
              </h3>
              <select
                value={uploadModule}
                onChange={(e) => setUploadModule(e.target.value)}
                className="text-[10.5px] border border-[#D2C9B8] rounded-[3px] px-2 py-1 bg-[#FBF9F5]"
                title="Module par défaut si import"
              >
                <option value="anapath">Anapath</option>
                <option value="endocrino-dermato">Endocrino-Dermato</option>
                <option value="hemato-onco">Hémato-Onco</option>
                <option value="neuro-neurochir">Neuro-NeuroChir</option>
              </select>
            </div>

            <div className="space-y-2.5 max-h-[70vh] overflow-y-auto pr-1">
              {(catalog?.drive_scans || []).map((f: any) => (
                <div
                  key={f.id}
                  className="p-3 rounded-[4px] border border-[#D2C9B8] bg-[#FBF9F5] space-y-2"
                >
                  <div className="flex items-center justify-between gap-2">
                    <ModuleBadge moduleId={f.module_id || 'anapath'} />
                    <span className="font-mono-tabular text-[10px] text-[#6F6A61]">
                      {(f.size / 1e6).toFixed(1)} Mo · {f.is_corrige ? 'Corrigé' : 'Annales'}
                    </span>
                  </div>
                  <div className="text-xs font-bold text-[#161615] break-words">{f.name}</div>
                  <button
                    disabled={preparingId === f.id}
                    onClick={() => handlePrepareDriveScan(f.id, f.module_id)}
                    className="w-full py-1.5 rounded-[4px] bg-[#161615] hover:bg-[#2F2C28] disabled:opacity-50 text-white text-[11px] font-semibold flex items-center justify-center gap-1.5 cursor-pointer"
                  >
                    {preparingId === f.id ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" /> Préparation…
                      </>
                    ) : (
                      'Ouvrir dans le Studio OCR →'
                    )}
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="lg:col-span-8 space-y-4">
            {!activeJob ? (
              <div className="bg-white border border-[#E5DFD3] rounded-[5px] p-10 text-center text-xs text-[#6F6A61]">
                Sélectionnez un PDF scanné à gauche (ex.{' '}
                <span className="font-semibold text-[#161615]">EXAMENS APS.pdf</span>,{' '}
                <span className="font-semibold text-[#161615]">QE PR HALAOUI.pdf</span>) ou importez
                votre propre document pour lancer la numérisation Vision IA page par page.
              </div>
            ) : (
              <div className="space-y-4">
                <div className="bg-white border border-[#E5DFD3] rounded-[5px] p-4 flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-bold text-[#161615]">{activeJob.filename}</div>
                    <div className="font-mono-tabular text-[11px] text-[#6F6A61]">
                      Page {jobPageIdx + 1} / {activeJob.pages.length} · Module :{' '}
                      {activeJob.module_id}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      disabled={jobPageIdx <= 0}
                      onClick={() => {
                        setJobPageIdx((i) => Math.max(0, i - 1));
                        setOcrDrafts([]);
                      }}
                      className="px-3 py-1.5 rounded-[4px] border border-[#D2C9B8] text-xs font-semibold disabled:opacity-40 cursor-pointer"
                    >
                      ← Préc.
                    </button>
                    <button
                      disabled={jobPageIdx >= activeJob.pages.length - 1}
                      onClick={() => {
                        setJobPageIdx((i) => Math.min(activeJob.pages.length - 1, i + 1));
                        setOcrDrafts([]);
                      }}
                      className="px-3 py-1.5 rounded-[4px] border border-[#D2C9B8] text-xs font-semibold disabled:opacity-40 cursor-pointer"
                    >
                      Suiv. →
                    </button>
                    <button
                      disabled={ocrBusy}
                      onClick={handleRunOcr}
                      className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-[4px] bg-[#6B1D2F] hover:bg-[#531523] disabled:opacity-50 text-white text-xs font-semibold cursor-pointer"
                    >
                      {ocrBusy ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Sparkles className="w-3.5 h-3.5" />
                      )}
                      Extraire par Vision IA
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-start">
                  <div className="bg-[#191715] border border-[#2F2B26] rounded-[4px] p-3">
                    {activeJob.pages[jobPageIdx] && (
                      <div className="bg-white rounded-[2px] p-1">
                        <img
                          src={activeJob.pages[jobPageIdx].image}
                          alt={`Page ${jobPageIdx + 1}`}
                          className="w-full object-contain max-h-[75vh]"
                        />
                      </div>
                    )}
                  </div>

                  <div className="space-y-3 max-h-[75vh] overflow-y-auto pr-1">
                    {ocrDrafts.length === 0 ? (
                      <div className="bg-white border border-[#E5DFD3] rounded-[5px] p-6 text-center text-xs text-[#6F6A61]">
                        Cliquez sur « Extraire par Vision IA » pour structurer ce scan avant enregistrement
                        en banque S7.
                      </div>
                    ) : (
                      ocrDrafts.map((d, di) => (
                        <div
                          key={di}
                          className="bg-[#FBF9F5] border border-[#D2C9B8] rounded-[4px] p-4 space-y-2 text-xs"
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-[#161615]">
                              Question #{d.question_number || di + 1} · {d.question_type}
                            </span>
                            <span className="font-mono-tabular font-bold text-[#2A5C48]">
                              Clé :{' '}
                              {(d.verified_correct_letters || d.marked_letters || []).join(' ; ') ||
                                '—'}
                            </span>
                          </div>
                          <div className="font-semibold text-[#161615]">{d.stem}</div>
                          {(d.options || []).map((o: any) => (
                            <div key={o.letter} className="text-[#6F6A61]">
                              <span className="font-bold text-[#161615]">{o.letter}.</span> {o.text}
                            </div>
                          ))}
                          {d.explanation && (
                            <div className="text-[#161615] bg-[#EFF5F2] border border-[#B8D4C8] p-2.5 rounded-[3px]">
                              {d.explanation}
                            </div>
                          )}
                          <button
                            onClick={() => saveDraftToQBank(d, di)}
                            className="w-full py-2 rounded-[4px] bg-[#6B1D2F] hover:bg-[#531523] text-white font-semibold flex items-center justify-center gap-1.5 cursor-pointer"
                          >
                            <Save className="w-3.5 h-3.5" /> Ajouter à la banque S7
                          </button>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

const SnQuestionVerifyCard: React.FC<{
  q: any;
  onSave: (q: any, newAnswersRaw: string, newExpl: string) => Promise<void>;
}> = ({ q, onSave }) => {
  const [ans, setAns] = useState((q.correct_answers_json || []).join(' ; '));
  const [expl, setExpl] = useState(q.explanation || '');

  useEffect(() => {
    setAns((q.correct_answers_json || []).join(' ; '));
    setExpl(q.explanation || '');
  }, [q.id, q.correct_answers_json, q.explanation]);

  return (
    <div className="bg-[#FBF9F5] border border-[#D2C9B8] rounded-[4px] p-5 space-y-3 text-xs">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[13px] font-bold text-[#161615]">
          Question #{q.question_number} extraite ·{' '}
          <span className="font-mono-tabular font-normal text-[#6F6A61]">{q.question_type}</span>
        </span>
        <VerificationBadge status={q.verification_status} />
      </div>

      <div className="text-[13px] font-semibold text-[#161615] leading-snug">{q.stem}</div>

      {(q.statements_json || []).length > 0 && (
        <div className="p-3 rounded-[4px] bg-white border border-[#E5DFD3] space-y-1 text-[#161615]">
          {q.statements_json.map((s: any) => (
            <div key={s.letter}>
              <span className="font-bold text-[#6F6A61]">{s.letter})</span> {s.text}
            </div>
          ))}
        </div>
      )}

      {(q.options_json || []).length > 0 && (
        <div className="space-y-1 text-[#6F6A61]">
          {q.options_json.map((o: any) => (
            <div key={o.letter}>
              <span className="font-bold text-[#161615]">{o.letter}.</span> {o.text}
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
        <div className="bg-white border border-[#D2C9B8] rounded-[4px] p-2.5">
          <label className="block text-[9px] font-bold uppercase tracking-wider text-[#6F6A61]">
            CLÉ VALIDÉE
          </label>
          <input
            value={ans}
            onChange={(e) => setAns(e.target.value)}
            className="w-full mt-1 font-mono-tabular text-[13.5px] font-bold text-[#2A5C48] bg-transparent focus:outline-none"
          />
        </div>
        <div className="sm:col-span-2 bg-white border border-[#D2C9B8] rounded-[4px] p-2.5">
          <label className="block text-[9px] font-bold uppercase tracking-wider text-[#6F6A61]">
            JUSTIFICATION CLINIQUE ARCHIVÉE
          </label>
          <textarea
            rows={2}
            value={expl}
            onChange={(e) => setExpl(e.target.value)}
            className="w-full mt-1 text-[12px] text-[#161615] bg-transparent focus:outline-none resize-none"
          />
        </div>
      </div>

      <div className="flex justify-end">
        <button
          onClick={() => onSave(q, ans, expl)}
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-[4px] bg-[#6B1D2F] hover:bg-[#531523] text-white text-[11.5px] font-semibold cursor-pointer transition"
        >
          <Save className="w-3.5 h-3.5" /> Valider & Mettre à jour
        </button>
      </div>
    </div>
  );
};
