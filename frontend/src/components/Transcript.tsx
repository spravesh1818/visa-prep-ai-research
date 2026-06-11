import { useEffect, useRef } from "react";
import type { TranscriptLine } from "../types";

export function Transcript({ lines }: { lines: TranscriptLine[] }) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines]);

  return (
    <section className="card transcript">
      <h3>Conversation</h3>
      <div className="transcript-scroll">
        {lines.length === 0 && (
          <p className="hint">Listening… the officer will greet you shortly.</p>
        )}
        {lines.map((line) => (
          <div
            key={line.id}
            className={`bubble ${line.role} ${line.final ? "" : "interim"}`}
          >
            <span className="speaker">
              {line.role === "officer" ? "Officer" : "You"}
            </span>
            <span className="text">{line.text}</span>
          </div>
        ))}
        <div ref={endRef} />
      </div>
    </section>
  );
}
