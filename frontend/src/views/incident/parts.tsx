import { Classes, Switch, Tag } from "@blueprintjs/core";
import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import type { CompanyComment, HazardTag, IncidentDetail } from "../../api/types";
import { Provenance, type ProvenanceTier } from "../../components/Provenance";
import { StatusTag } from "../../components/StatusTag";
import { Highlighted } from "../../components/text";

export function Section({ title, tier, method, actions, children }: {
  title: string; tier?: ProvenanceTier; method?: string; actions?: ReactNode; children: ReactNode;
}) {
  return (
    <section className="detail-section">
      <header className="detail-section-head">
        <h3>{title}</h3>
        {tier && <Provenance tier={tier} method={method} />}
        <span className="spacer" />
        {actions}
      </header>
      {children}
    </section>
  );
}

export function Narrative({ text, hazards }: { text: string; hazards: HazardTag[] }) {
  const [highlight, setHighlight] = useState(false);
  const phrases = hazards.flatMap((h) => h.evidence);
  return (
    <Section title="Narrative" tier="reported" actions={phrases.length > 0 && (
      <Switch className="inline-switch" checked={highlight} label="Mark hazard phrases"
        onChange={(e) => setHighlight(e.currentTarget.checked)} />
    )}>
      <div className="narrative">
        {highlight ? <Highlighted text={text} terms={phrases} /> : text}
      </div>
    </Section>
  );
}

export function HazardEvidence({ hazards, method }: { hazards: HazardTag[]; method?: string }) {
  return (
    <Section title="Inferred hazards" tier="inferred" method={method ?? hazards[0]?.method}>
      {hazards.length === 0 ? (
        <p className={Classes.TEXT_MUTED}>No hazard phrases matched this narrative.</p>
      ) : (
        <ul className="hazard-evidence">
          {hazards.map((h) => (
            <li key={h.hazard}>
              <Tag minimal intent="warning">{h.label}</Tag>
              <span className="evidence-label">triggered by</span>
              {h.evidence.map((e, i) => <q key={i} className="evidence-phrase">{e}</q>)}
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

export function CompanyComments({ comments, raw }: { comments: CompanyComment[]; raw: string | null }) {
  return (
    <Section title={`Manufacturer responses (${comments.length})`} tier="reported">
      {comments.length === 0 ? (
        <p className={Classes.TEXT_MUTED}>No manufacturer response published.</p>
      ) : comments.map((c, i) => (
        <blockquote key={i} className="company-comment">
          <div className="company-comment-head">
            <strong>{c.company ?? "Company"}</strong>
            {c.date && <span className={Classes.TEXT_MUTED}>{c.date}</span>}
          </div>
          <div className="narrative">{c.text}</div>
        </blockquote>
      ))}
      {raw && comments.length > 1 && (
        <details className="raw-comments">
          <summary className={Classes.TEXT_MUTED}>Unparsed field as published</summary>
          <div className="narrative">{raw}</div>
        </details>
      )}
    </Section>
  );
}

export function AnalystContext({ detail }: { detail: IncidentDetail }) {
  const { investigations, relation_reviews } = detail.analyst;
  const confirmed = relation_reviews.filter((r) => r.verdict === "confirmed").length;
  return (
    <Section title="Analyst context" tier="analyst">
      {investigations.length === 0 ? (
        <p className={Classes.TEXT_MUTED}>Not in any investigation.</p>
      ) : (
        <ul className="plain-list">
          {investigations.map((inv) => (
            <li key={inv.id}>
              <Link to={`/investigations/${inv.id}`}>#{inv.id} {inv.title}</Link> <StatusTag status={inv.status} />
            </li>
          ))}
        </ul>
      )}
      {relation_reviews.length > 0 && (
        <p className={Classes.TEXT_MUTED}>
          {relation_reviews.length} relationship review{relation_reviews.length === 1 ? "" : "s"}, {confirmed} confirmed.
        </p>
      )}
    </Section>
  );
}
