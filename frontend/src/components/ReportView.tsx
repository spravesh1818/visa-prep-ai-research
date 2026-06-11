import type { InterviewReport } from "../types";

function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function ReportView({ report }: { report: InterviewReport }) {
  return (
    <section className="card report">
      <div className="report-head">
        <h3>{report.display_name} — Report</h3>
        <div className={`score-badge band-${report.recommendation_band}`}>
          <span className="score">{pct(report.overall_score)}</span>
          <span className="band">{report.recommendation_band}</span>
        </div>
      </div>

      <p className="recommendation">{report.recommendation}</p>
      <p className="summary">{report.summary}</p>

      {report.university_assessment && (
        <div className="uni">
          <strong>University:</strong>{" "}
          {report.university_assessment.matched_name ??
            report.university_assessment.raw_name ??
            "—"}{" "}
          <span className={`tier tier-${report.university_assessment.tier}`}>
            {report.university_assessment.tier}
          </span>
        </div>
      )}

      <div className="cols">
        <div>
          <h4>Strengths</h4>
          <ul>
            {report.strengths.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
            {report.strengths.length === 0 && <li className="hint">None noted</li>}
          </ul>
        </div>
        <div>
          <h4>Weaknesses</h4>
          <ul>
            {report.weaknesses.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
            {report.weaknesses.length === 0 && <li className="hint">None noted</li>}
          </ul>
        </div>
      </div>

      <h4>Topic scores</h4>
      <table className="topics">
        <thead>
          <tr>
            <th>Topic</th>
            <th>Score</th>
            <th>Probes</th>
          </tr>
        </thead>
        <tbody>
          {report.topic_results.map((t) => (
            <tr key={t.topic_id}>
              <td>{t.label}</td>
              <td>{pct(t.score)}</td>
              <td>{t.probes_used}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {report.red_flags.length > 0 && (
        <div className="flags">
          <h4>Red flags</h4>
          <ul>
            {report.red_flags.map((f, i) => (
              <li key={i}>{f}</li>
            ))}
          </ul>
        </div>
      )}

      <p className="disclaimer">{report.disclaimer}</p>
    </section>
  );
}
