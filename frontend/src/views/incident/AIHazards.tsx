import { Callout, Tag } from "@blueprintjs/core";
import type { AIHazardResult } from "../../api/types";
import { AIClassifyButton } from "../../components/AIClassifyButton";
import { Section } from "./parts";

export function AIHazards({ reportNo, results }: { reportNo: string; results: AIHazardResult[] }) {
  return <div className="ai-hazards"><Section title="AI inferred hazards" tier="inferred">
    <AIClassifyButton reportNos={[reportNo]} />
    {results.length === 0 && <p className="muted">No AI classification yet.</p>}
    {results.map((result) => <article key={result.model}>
      <p><strong>AI-generated · {result.model} · {result.prompt_version}</strong></p>
      <p className="muted">{result.classified_by?.display_name ?? "Unknown user"} · {result.classified_at}</p>
      {result.stale && <Callout intent="warning" icon="history">
        The report changed after this classification. Its quotes were checked against the earlier version. Classify again to refresh.
      </Callout>}
      {result.status === "error" ? <Callout intent="danger">{result.error}</Callout> : <>
        {result.hazards.length === 0 && <p>No hazards with verified evidence.</p>}
        {result.hazards.map((hazard) => <div key={hazard.hazard}>
          <Tag intent="primary">{hazard.label}</Tag>
          {hazard.evidence.map((quote) => <blockquote key={quote}>{quote}</blockquote>)}
        </div>)}
      </>}
      <details><summary>{result.dropped.length} dropped claims</summary>
        {result.dropped.map((drop, i) => <div key={i}><p>{drop.reason}</p><pre>{JSON.stringify(drop.claim, null, 2)}</pre></div>)}
      </details>
    </article>)}
  </Section></div>;
}
