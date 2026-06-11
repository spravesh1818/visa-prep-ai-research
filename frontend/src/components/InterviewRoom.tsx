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
      className="room"
    >
      <RoomAudioRenderer />
      <RoomInner onLeave={onLeave} />
    </LiveKitRoom>
  );
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
    }

    function onData(payload: Uint8Array, _p?: Participant, _k?: unknown, topic?: string) {
      if (topic && topic !== "interview") return;
      try {
        const msg = JSON.parse(new TextDecoder().decode(payload));
        if (msg.type === "session" && msg.session_id) {
          setSessionId(msg.session_id);
          setStatus("in_progress");
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

  // Poll for the final report once we know the session id.
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
    <div className="page room-layout">
      <header className="room-header">
        <div>
          <h2>Interview in progress</h2>
          <span className={`status status-${status}`}>{status.replace("_", " ")}</span>
        </div>
        <div className="controls">
          <button className={isMicrophoneEnabled ? "mic on" : "mic off"} onClick={toggleMic}>
            {isMicrophoneEnabled ? "Mute mic" : "Unmute mic"}
          </button>
          <button className="ghost" onClick={leave}>
            End interview
          </button>
        </div>
      </header>

      <div className="room-body">
        <Transcript lines={lines} />
        {report ? (
          <ReportView report={report} />
        ) : (
          <aside className="card report-pending">
            <h3>Report</h3>
            <p>
              The scored report will appear here automatically once the interview
              concludes.
            </p>
            {sessionId && <p className="hint">Session: {sessionId}</p>}
          </aside>
        )}
      </div>
    </div>
  );
}
