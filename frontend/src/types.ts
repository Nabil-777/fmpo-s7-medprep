export type NavTab = 'dashboard' | 'courses' | 'clinical' | 'exams' | 'radar' | 'scans';

export interface ModuleInfo {
  id: string;
  name: string;
  short_name: string;
  sub_disciplines: string[];
  exam_format: string;
  exam_duration_min: number;
  scoring_rule: string;
  accent_color: string;
  question_count: number;
  sn2025_count: number;
  course_count: number;
  clinical_cases_count: number;
  course_mastery_avg: number;
  attempts_total: number;
  attempts_accuracy: number | null;
}

export interface CourseItem {
  id: number;
  module_id: string;
  sub_discipline: string;
  professor: string;
  canonical_title: string;
  promo_status: string;
  upload_flag: string;
  mastery_score: number;
  reps: number;
  lapses: number;
  last_reviewed_at: string | null;
  next_review_at: string | null;
  high_yield_points: string[];
  notes_markdown: string;
  exam_frequency: string;
  file_count?: number;
  summary_count?: number;
  question_count?: number;
}

export interface DriveFileItem {
  id: string;
  name: string;
  path: string;
  size: number;
  module_id: string | null;
  category: string;
  professor: string | null;
  local_path: string | null;
  text_chars: number;
  page_count: number;
  is_scanned: number;
  is_corrige: number;
  version_tag: string | null;
}

export interface QuestionOption {
  letter: string;
  text: string;
}

export interface QuestionItem {
  id: number;
  external_key: string;
  module_id: string;
  sub_discipline: string;
  course_id: number | null;
  course_title?: string | null;
  professor: string | null;
  source_label: string;
  exam_year: string | null;
  session: string;
  question_number: number | null;
  vignette_group_id: string | null;
  vignette_text: string | null;
  question_type: 'qcm_multi' | 'qcm_group' | 'qroc' | 'synthesis' | string;
  stem: string;
  statements_json: QuestionOption[];
  options_json: QuestionOption[];
  correct_answers_json: string[];
  rubric_json: { points?: string[] };
  explanation: string;
  verification_status: string;
  scan_page_image: string | null;
  frequency_tag: string;
}

export interface AttemptResult {
  is_correct: boolean;
  partial_score: number;
  max_score: number;
  grading_note: string;
  matched_points?: string[];
  missed_points?: string[];
  correct_answers: string[];
  rubric: { points?: string[] };
  explanation: string;
  verification_status: string;
  scan_page_image: string | null;
}

export interface ClinicalStep {
  step_number: number;
  step_type: string;
  prompt: string;
  clinical_reveal: string;
  question_format: string;
  options: QuestionOption[];
  correct_answers: string[];
  red_flags: string[];
  teaching_pearl: string;
  points: number;
}

export interface ClinicalCaseItem {
  id: number;
  slug: string;
  module_id: string;
  sub_discipline: string;
  course_id: number | null;
  course_title?: string | null;
  title: string;
  difficulty: string;
  source_tag: string;
  patient_summary: string;
  vitals_json: Record<string, string>;
  steps_json: ClinicalStep[];
  takeaway_points: string[];
  best_ratio?: number | null;
  attempt_count?: number;
}
