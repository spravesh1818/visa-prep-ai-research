import { useEffect, useState } from "react";
import { fetchConfig, requestVoiceToken } from "./api";
import type { ConfigResponse, OntologyInfo, VoiceTokenResponse } from "./types";
import { InterviewRoom } from "./components/InterviewRoom";

function interviewKey(o: OntologyInfo): string {
  return `${o.country}::${o.visa_type}`;
}

export default function App() {
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string>("");
  const [token, setToken] = useState<VoiceTokenResponse | null>(null);
  const [connecting, setConnecting] = useState(false);

  useEffect(() => {
    fetchConfig()
      .then((c) => {
        setConfig(c);
        if (c.supported_interviews.length > 0) {
          setSelected(interviewKey(c.supported_interviews[0]));
        }
      })
      .catch((e) => setError(String(e)));
  }, []);

  async function startInterview() {
    if (!config || !selected) return;
    const target = config.supported_interviews.find(
      (o) => interviewKey(o) === selected,
    );
    if (!target) return;
    setConnecting(true);
    setError(null);
    try {
      const t = await requestVoiceToken(target.country, target.visa_type);
      setToken(t);
    } catch (e) {
      setError(String(e));
    } finally {
      setConnecting(false);
    }
  }

  if (token) {
    return (
      <InterviewRoom
        token={token}
        onLeave={() => setToken(null)}
      />
    );
  }

  return (
    <div className="mx-auto max-w-[1100px] px-5 py-8 pb-16">
      <header className="mb-section">
        <h1 className="text-[2rem] font-medium leading-tight text-ink md:text-[2.5rem]">
          Visa Interview — Voice
        </h1>
        <p className="mt-3 max-w-xl text-base leading-relaxed text-mute">
          A realistic, ontology-driven mock visa interview. Speak naturally; the
          officer will probe your answers and produce a scored report.
        </p>
      </header>

      {error && (
        <div className="mb-6 border border-sale/30 bg-sale/10 px-4 py-3 text-sm text-sale-deep">
          {error}
        </div>
      )}

      {!config && !error && (
        <div className="border border-hairline bg-soft-cloud px-4 py-3 text-sm text-charcoal">
          Loading configuration…
        </div>
      )}

      {config && (
        <div className="mt-6 max-w-md border border-hairline bg-canvas p-6">
          {!config.voice_enabled && (
            <div className="mb-6 border border-amber-500/30 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              Voice is not configured on the backend. Set LiveKit, Deepgram, and
              ElevenLabs keys to enable the live interview.
            </div>
          )}

          <label className="mb-6 flex flex-col gap-2 text-sm font-medium text-mute">
            Interview type
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
              className="h-12 rounded-search border border-hairline bg-soft-cloud px-4 text-base font-normal text-ink outline-none focus:border-ink focus:ring-2 focus:ring-soft-cloud"
            >
              {config.supported_interviews.map((o) => (
                <option key={interviewKey(o)} value={interviewKey(o)}>
                  {o.display_name} ({o.country} {o.visa_type})
                </option>
              ))}
            </select>
          </label>

          <button
            type="button"
            className="h-12 w-full rounded-pill bg-ink px-8 text-base font-medium text-white transition active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
            disabled={!config.voice_enabled || connecting || !selected}
            onClick={startInterview}
          >
            {connecting ? "Connecting…" : "Start voice interview"}
          </button>

          <p className="mt-4 text-xs text-mute">
            Active model: {String((config.llm as { model?: string }).model ?? "—")} ·
            Backend checkpointer: {config.checkpointer_backend}
          </p>
        </div>
      )}
    </div>
  );
}
