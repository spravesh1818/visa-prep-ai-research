import { useCallback, useEffect, useRef, useState } from "react";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useLocalParticipant,
  useRoomContext,
} from "@livekit/components-react";
import { RoomEvent, type TranscriptionSegment, Participant } from "livekit-client";
import type {
  InterviewReport,
  TranscriptLine,
  VoiceTokenResponse,
} from "../types";
import { fetchReport } from "../api";
import { Transcript } from "./Transcript";
import { ReportView } from "./ReportView";

interface Props {
  token: VoiceTokenResponse;
  onLeave: () => void;
}

export function InterviewRoom({ token, onLeave }: Props) {
  return (
    <LiveKitRoom
      serverUrl={token.url}
      token={token.token}
      connect
      audio
      video={false}
      onDisconnected={onLeave}
      className="min-h-screen bg-canvas"
    >
      <RoomAudioRenderer />
      <RoomInner onLeave={onLeave} />
    </LiveKitRoom>
  );
}

function statusLabel(status: string): string {
  return status.replace(/_/g, " ");
}

function statusColorClass(status: string): string {
  if (status === "completed") return "text-success";
  if (status === "officer_speaking") return "text-info";
  return "text-mute";
}

function RoomInner({ onLeave }: { onLeave: () => void }) {
  const room = useRoomContext();
  const { localParticipant, isMicrophoneEnabled } = useLocalParticipant();
  const [lines, setLines] = useState<TranscriptLine[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [report, setReport] = useState<InterviewReport | null>(null);
  const [status, setStatus] = useState<string>("connecting");
  const linesRef = useRef<Map<string, TranscriptLine>>(new Map());

  const flush = useCallback(() => {
    setLines(Array.from(linesRef.current.values()));
  }, []);

  useEffect(() => {
    function onTranscription(
      segments: TranscriptionSegment[],
      participant?: Participant,
    ) {
      const isLocal = participant?.identity === localParticipant.identity;
      const role = isLocal ? "applicant" : "officer";
      for (const seg of segments) {
        linesRef.current.set(seg.id, {
          id: seg.id,
          role,
          text: seg.text,
          final: seg.final,
        });
      }
      flush();

      if (!isLocal && segments.length > 0) {
        const anyInterim = segments.some((s) => !s.final);
        setStatus(anyInterim ? "officer_speaking" : "awaiting_you");
      } else if (isLocal && segments.some((s) => !s.final)) {
        setStatus("listening");
      }
    }

    function onData(payload: Uint8Array, _p?: Participant, _k?: unknown, topic?: string) {
      if (topic && topic !== "interview") return;
      try {
        const msg = JSON.parse(new TextDecoder().decode(payload));
        if (msg.type === "session" && msg.session_id) {
          setSessionId(msg.session_id);
          setStatus("awaiting_you");
        }
      } catch {
        /* ignore malformed data */
      }
    }

    room.on(RoomEvent.TranscriptionReceived, onTranscription);
    room.on(RoomEvent.DataReceived, onData);
    return () => {
      room.off(RoomEvent.TranscriptionReceived, onTranscription);
      room.off(RoomEvent.DataReceived, onData);
    };
  }, [room, localParticipant, flush]);

  useEffect(() => {
    if (!sessionId || report) return;
    let active = true;
    const timer = setInterval(async () => {
      try {
        const res = await fetchReport(sessionId);
        if (!active) return;
        setStatus(res.status);
        if (res.status === "completed" && res.report) {
          setReport(res.report);
          clearInterval(timer);
        }
      } catch {
        /* not ready yet */
      }
    }, 4000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [sessionId, report]);

  async function toggleMic() {
    await localParticipant.setMicrophoneEnabled(!isMicrophoneEnabled);
  }

  function leave() {
    room.disconnect();
    onLeave();
  }

  return (
    <div className="mx-auto max-w-[1100px] px-5 py-8 pb-16">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-hairline pb-6">
        <div>
          <h2 className="text-2xl font-medium text-ink">Interview in progress</h2>
          <span
            className={`mt-1 inline-block text-sm capitalize ${statusColorClass(status)}`}
          >
            {statusLabel(status)}
          </span>
        </div>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            className={`h-12 rounded-pill px-6 text-sm font-medium transition active:scale-[0.98] ${
              isMicrophoneEnabled
                ? "bg-sale text-white"
                : "bg-success text-white"
            }`}
            onClick={toggleMic}
          >
            {isMicrophoneEnabled ? "Mute mic" : "Unmute mic"}
          </button>
          <button
            type="button"
            className="h-12 rounded-pill border border-hairline bg-soft-cloud px-6 text-sm font-medium text-ink transition active:scale-[0.98]"
            onClick={leave}
          >
            End interview
          </button>
        </div>
      </header>

      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-2">
        <Transcript lines={lines} />
        {report ? (
          <ReportView report={report} />
        ) : (
          <aside className="border border-hairline bg-soft-cloud p-6">
            <h3 className="mb-3 text-xl font-medium text-ink">Report</h3>
            <p className="text-sm leading-relaxed text-charcoal">
              The scored report will appear here automatically once the interview
              concludes. The transcript will include question types and probe tags.
            </p>
            {sessionId && (
              <p className="mt-4 text-xs text-mute">Session: {sessionId}</p>
            )}
          </aside>
        )}
      </div>
    </div>
  );
}
