import { useEffect, useRef } from "react";
import type { TranscriptLine } from "../types";

export function Transcript({ lines }: { lines: TranscriptLine[] }) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines]);

  return (
    <section className="border border-hairline bg-canvas p-6">
      <h3 className="mb-4 text-xl font-medium text-ink">Conversation</h3>
      <div className="flex max-h-[60vh] flex-col gap-3 overflow-y-auto pr-1">
        {lines.length === 0 && (
          <p className="text-sm text-mute">
            Listening… the officer will greet you shortly.
          </p>
        )}
        {lines.map((line) => (
          <div
            key={line.id}
            className={`flex max-w-[92%] flex-col gap-1 rounded-search border px-3 py-2 ${
              line.role === "officer"
                ? "self-start border-hairline bg-soft-cloud"
                : "self-end border-hairline-soft bg-canvas"
            } ${line.final ? "" : "opacity-60 italic"}`}
          >
            <span className="text-xs font-medium uppercase tracking-wide text-mute">
              {line.role === "officer" ? "Officer" : "You"}
            </span>
            <span className="text-sm leading-relaxed text-ink">{line.text}</span>
          </div>
        ))}
        <div ref={endRef} />
      </div>
    </section>
  );
}
