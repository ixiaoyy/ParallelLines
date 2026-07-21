export type DailyReportStyle = "concise" | "detailed" | "result" | "process";
export type DailyReportProviderMode = "ai" | "local_fallback";

export interface DailyReportInput {
  work_date: string;
  recurring_work: string[];
  extra_work: string[];
  risks: string[];
  tomorrow_plan: string[];
  style: DailyReportStyle;
}

export interface DailyReportProfile {
  custom_prompt: string;
  preferences: Record<string, unknown>;
  prompt_version: number;
  ai_enabled: boolean;
  provider_mode: DailyReportProviderMode;
  model_name: string;
  privacy_notice: string;
  updated_at: string;
}

export interface DailyReportProfileUpdateRequest {
  custom_prompt: string;
  expected_version: number;
}

export interface DailyReportPreferenceAcceptRequest {
  requirement: string;
  expected_version: number;
}

export interface DailyReportMessage {
  id: string;
  sequence: number;
  role: "user" | "assistant";
  content: string;
  preference_suggestion: string | null;
  created_at: string;
}

export interface DailyReportSession {
  id: string;
  work_date: string;
  status: "active" | "confirmed";
  input: DailyReportInput;
  current_draft: string;
  prompt_version: number;
  version: number;
  model_name: string;
  provider_mode: DailyReportProviderMode;
  messages: DailyReportMessage[];
  created_at: string;
  updated_at: string;
}

export interface DailyReportFollowupRequest {
  message: string;
  current_content?: string;
  expected_version: number;
}

export interface DailyReportConfirmRequest {
  content: string;
  expected_version: number;
}

export interface DailyReportRecord {
  id: string;
  session_id: string;
  work_date: string;
  content: string;
  input: DailyReportInput;
  prompt_version: number;
  model_name: string;
  created_at: string;
  updated_at: string;
}

export const DAILY_REPORT_STYLE_OPTIONS: ReadonlyArray<{
  value: DailyReportStyle;
  label: string;
}> = [
  { value: "detailed", label: "详细自然" },
  { value: "concise", label: "简洁直接" },
  { value: "result", label: "结果导向" },
  { value: "process", label: "过程清晰" },
];
