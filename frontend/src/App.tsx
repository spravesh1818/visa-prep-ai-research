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
    <div className="page">
      <header className="hero">
        <h1>Visa Interview — Voice</h1>
        <p className="subtitle">
          A realistic, ontology-driven mock visa interview. Speak naturally; the
          officer will probe your answers and produce a scored report.
        </p>
      </header>

      {error && <div className="banner error">{error}</div>}

      {!config && !error && <div className="banner">Loading configuration…</div>}

      {config && (
        <div className="card setup">
          {!config.voice_enabled && (
            <div className="banner warn">
              Voice is not configured on the backend. Set LiveKit, Deepgram, and
              ElevenLabs keys to enable the live interview.
            </div>
          )}

          <label className="field">
            <span>Interview type</span>
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
            >
              {config.supported_interviews.map((o) => (
                <option key={interviewKey(o)} value={interviewKey(o)}>
                  {o.display_name} ({o.country} {o.visa_type})
                </option>
              ))}
            </select>
          </label>

          <button
            className="primary"
            disabled={!config.voice_enabled || connecting || !selected}
            onClick={startInterview}
          >
            {connecting ? "Connecting…" : "Start voice interview"}
          </button>

          <p className="hint">
            Active model: {String((config.llm as { model?: string }).model ?? "—")} ·
            Backend checkpointer: {config.checkpointer_backend}
          </p>
        </div>
      )}
    </div>
  );
}
