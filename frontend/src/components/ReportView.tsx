import type { InterviewReport, TranscriptEntry, TurnKind } from "../types";

function formatOverallScore(value: number): string {
  return `${Math.round(value)}/100`;
}

function formatTopicScore(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function bandColorClass(band: string): string {
  const key = band.toLowerCase();
  if (key === "strong" || key === "likely") return "text-success";
  if (key === "borderline") return "text-amber-600";
  return "text-sale";
}

function turnKindLabel(entry: TranscriptEntry): string | null {
  if (entry.role !== "officer" || !entry.turn_kind) return null;
  switch (entry.turn_kind) {
    case "greeting":
      return "Greeting";
    case "question":
      return "Question";
    case "probe":
      return "Follow-up probe";
    case "closing":
      return "Closing";
    default:
      return null;
  }
}

function TurnPill({ entry }: { entry: TranscriptEntry }) {
  const label = turnKindLabel(entry);
  if (!label) return null;

  const kind = entry.turn_kind as TurnKind;
  let pillClass =
    "inline-flex items-center rounded-pill border border-hairline bg-soft-cloud px-3 py-0.5 text-xs font-medium text-ink";

  if (kind === "probe") {
    pillClass =
      "inline-flex items-center rounded-pill border border-info/30 bg-info/10 px-3 py-0.5 text-xs font-medium text-info-deep";
  } else if (kind === "closing") {
    pillClass =
      "inline-flex items-center rounded-pill border border-hairline bg-canvas px-3 py-0.5 text-xs font-medium text-mute";
  }

  return (
    <div className="mb-1 flex flex-wrap items-center gap-2">
      <span className={pillClass}>{label}</span>
      {entry.topic_label && kind !== "greeting" && kind !== "closing" && (
        <span className="text-xs font-medium text-mute">{entry.topic_label}</span>
      )}
    </div>
  );
}

export function ReportView({ report }: { report: InterviewReport }) {
  return (
    <section className="border border-hairline bg-canvas p-6">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4 border-b border-hairline pb-6">
        <h3 className="text-2xl font-medium leading-tight text-ink">
          {report.display_name} — Report
        </h3>
        <div className="flex flex-col items-center rounded-pill bg-ink px-5 py-2">
          <span className="text-2xl font-semibold text-white">
            {formatOverallScore(report.overall_score)}
          </span>
          <span
            className={`text-xs font-medium uppercase tracking-wide ${bandColorClass(report.recommendation_band)}`}
          >
            {report.recommendation_band}
          </span>
        </div>
      </div>

      <p className="mb-2 text-base font-medium text-ink">{report.recommendation}</p>
      <p className="mb-6 text-base leading-relaxed text-charcoal">{report.summary}</p>

      {report.university_assessment && (
        <div className="mb-6 border border-hairline bg-soft-cloud px-4 py-3 text-sm">
          <strong className="font-medium text-ink">University:</strong>{" "}
          <span className="text-charcoal">
            {report.university_assessment.matched_name ??
              report.university_assessment.raw_name ??
              "—"}
          </span>{" "}
          <span
            className={`ml-1 inline-flex rounded-pill border border-hairline px-2 py-0.5 text-xs font-medium ${
              ["top", "high"].includes(report.university_assessment.tier)
                ? "text-success"
                : ["low", "diploma_mill"].includes(report.university_assessment.tier)
                  ? "text-sale"
                  : "text-mute"
            }`}
          >
            {report.university_assessment.tier}
          </span>
        </div>
      )}

      {report.transcript.length > 0 && (
        <div className="mb-8">
          <h4 className="mb-4 text-base font-medium text-ink">Transcript</h4>
          <div className="max-h-80 space-y-3 overflow-y-auto border border-hairline bg-soft-cloud p-4">
            {report.transcript.map((entry, i) => (
              <div
                key={i}
                className={`rounded-search border px-3 py-2 ${
                  entry.role === "officer"
                    ? "border-hairline bg-canvas"
                    : "ml-6 border-hairline-soft bg-canvas"
                }`}
              >
                {entry.role === "officer" && <TurnPill entry={entry} />}
                <div className="flex flex-col gap-0.5">
                  <span className="text-xs font-medium uppercase tracking-wide text-mute">
                    {entry.role === "officer" ? "Officer" : "You"}
                  </span>
                  <p className="text-sm leading-relaxed text-ink">{entry.content}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mb-8 grid grid-cols-1 gap-6 md:grid-cols-2">
        <div>
          <h4 className="mb-3 text-base font-medium text-ink">Strengths</h4>
          <ul className="space-y-2 text-sm text-charcoal">
            {report.strengths.map((s, i) => (
              <li key={i} className="border-b border-hairline-soft pb-2">
                {s}
              </li>
            ))}
            {report.strengths.length === 0 && (
              <li className="text-mute">None noted</li>
            )}
          </ul>
        </div>
        <div>
          <h4 className="mb-3 text-base font-medium text-ink">Weaknesses</h4>
          <ul className="space-y-2 text-sm text-charcoal">
            {report.weaknesses.map((w, i) => (
              <li key={i} className="border-b border-hairline-soft pb-2">
                {w}
              </li>
            ))}
            {report.weaknesses.length === 0 && (
              <li className="text-mute">None noted</li>
            )}
          </ul>
        </div>
      </div>

      <h4 className="mb-3 text-base font-medium text-ink">Topic scores</h4>
      <table className="mb-6 w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-hairline text-left">
            <th className="py-2 pr-4 font-medium text-ink">Topic</th>
            <th className="py-2 pr-4 font-medium text-ink">Score</th>
            <th className="py-2 font-medium text-ink">Probes</th>
          </tr>
        </thead>
        <tbody>
          {report.topic_results.map((t) => (
            <tr key={t.topic_id} className="border-b border-hairline-soft">
              <td className="py-2 pr-4 text-charcoal">{t.label}</td>
              <td className="py-2 pr-4 text-ink">{formatTopicScore(t.score)}</td>
              <td className="py-2 text-charcoal">{t.probes_used}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {report.red_flags.length > 0 && (
        <div className="mb-6 border border-sale/20 bg-sale/5 px-4 py-3">
          <h4 className="mb-2 text-base font-medium text-sale">Red flags</h4>
          <ul className="space-y-1 text-sm text-sale-deep">
            {report.red_flags.map((f, i) => (
              <li key={i}>{f}</li>
            ))}
          </ul>
        </div>
      )}

      <p className="border-t border-hairline pt-4 text-xs leading-relaxed text-mute">
        {report.disclaimer}
      </p>
    </section>
  );
}
