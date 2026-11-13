async function req<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(txt || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  dashboard: () => req<any>('/api/dashboard'),
  courses: (params: Record<string, string | boolean>) => {
    const sp = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== '' && v !== false && v !== 'all') sp.set(k, String(v));
    });
    return req<any>(`/api/courses?${sp.toString()}`);
  },
  courseDetail: (id: number) => req<any>(`/api/courses/${id}`),
  reviewCourse: (id: number, rating: string, notes_markdown?: string) =>
    req<any>(`/api/courses/${id}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rating, notes_markdown }),
    }),
  filePages: (fileId: string) => req<any>(`/api/files/${fileId}/pages`),
  questionSources: () => req<any>('/api/questions/sources'),
  questions: (params: Record<string, string | number | boolean>) => {
    const sp = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== '' && v !== false && v !== 'all' && v !== undefined) sp.set(k, String(v));
    });
    return req<any>(`/api/questions?${sp.toString()}`);
  },
  attemptQuestion: (
    qid: number,
    payload: {
      session_id: string;
      mode: string;
      selected_answers?: string[];
      written_answer?: string;
    },
  ) =>
    req<any>(`/api/questions/${qid}/attempt`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  radar: () => req<any>('/api/analytics/radar'),
  clinicalCases: (module_id?: string) =>
    req<any>(`/api/clinical-cases${module_id && module_id !== 'all' ? `?module_id=${module_id}` : ''}`),
  clinicalCase: (slug: string) => req<any>(`/api/clinical-cases/${slug}`),
  recordCaseAttempt: (caseId: number, score: number, max_score: number, answers: Record<string, unknown>) =>
    req<any>(`/api/clinical-cases/${caseId}/attempt`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ score, max_score, answers }),
    }),
  scanCatalog: () => req<any>('/api/scans/catalog'),
  sn2025Batch: (prefix: string) => req<any>(`/api/scans/sn2025-pages/${prefix}`),
  prepareDriveScan: (fileId: string) =>
    req<any>(`/api/scans/prepare/${fileId}`, { method: 'POST' }),
  ocrJobPage: (jobId: string, pageNum: number, moduleHint: string) =>
    req<any>(`/api/scans/jobs/${jobId}/ocr/${pageNum}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ module_hint: moduleHint }),
    }),
  uploadScan: (formData: FormData) =>
    req<any>('/api/scans/upload', { method: 'POST', body: formData }),
  saveQuestion: (payload: any) =>
    req<any>('/api/scans/save-question', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
};
