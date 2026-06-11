import type {
  ConfigResponse,
  ReportResponse,
  VoiceTokenResponse,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "";

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export async function fetchConfig(): Promise<ConfigResponse> {
  return jsonOrThrow<ConfigResponse>(await fetch(`${BASE}/config`));
}

export async function requestVoiceToken(
  country: string,
  visaType: string,
  candidateProfile?: Record<string, unknown>,
): Promise<VoiceTokenResponse> {
  const res = await fetch(`${BASE}/voice/token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      country,
      visa_type: visaType,
      candidate_profile: candidateProfile,
    }),
  });
  return jsonOrThrow<VoiceTokenResponse>(res);
}

export async function fetchReport(sessionId: string): Promise<ReportResponse> {
  return jsonOrThrow<ReportResponse>(
    await fetch(`${BASE}/interview/${sessionId}/report`),
  );
}
