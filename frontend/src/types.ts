export interface OntologyInfo {
  country: string;
  visa_type: string;
  display_name: string;
}

export interface ConfigResponse {
  llm: Record<string, unknown>;
  checkpointer_backend: string;
  max_probes_per_topic: number;
  supported_interviews: OntologyInfo[];
  voice_enabled: boolean;
}

export interface VoiceTokenResponse {
  url: string;
  token: string;
  room: string;
  identity: string;
}

export interface TopicResult {
  topic_id: string;
  label: string;
  score: number;
  probes_used: number;
  notes?: string;
}

export interface UniversityAssessment {
  raw_name?: string | null;
  matched_name?: string | null;
  tier: string;
  confidence: number;
  rationale?: string;
}

export interface InterviewReport {
  session_id: string;
  country: string;
  visa_type: string;
  display_name: string;
  overall_score: number;
  recommendation_band: string;
  recommendation: string;
  summary: string;
  strengths: string[];
  weaknesses: string[];
  topic_results: TopicResult[];
  red_flags: string[];
  consistency_findings: string[];
  coaching_signal?: string;
  university_assessment?: UniversityAssessment | null;
  probing_summary?: string;
  transcript: { role: string; content: string }[];
  model_info: Record<string, unknown>;
  disclaimer: string;
}

export interface ReportResponse {
  session_id: string;
  status: string;
  report: InterviewReport | null;
}

export type TranscriptRole = "officer" | "applicant";

export interface TranscriptLine {
  id: string;
  role: TranscriptRole;
  text: string;
  final: boolean;
}
