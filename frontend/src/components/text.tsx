import { Fragment } from "react";
import { Link } from "react-router-dom";
import { splitReportNos } from "../domain/reportNo";

export function ReportLink({ reportNo, tab }: { reportNo: string; tab?: "related" | "source" }) {
  return (
    <Link className="report-link mono" to={`/incidents/${reportNo}${tab ? `/${tab}` : ""}`}>
      {reportNo}
    </Link>
  );
}

function decodeEntities(text: string): string {
  if (!text.includes("&")) return text;
  return new DOMParser().parseFromString(text, "text/html").documentElement.textContent ?? text;
}

export function Marked({ html }: { html: string }) {
  const parts = html.split(/(<mark>|<\/mark>)/).map((p) => (p === "<mark>" || p === "</mark>" ? p : decodeEntities(p)));
  let inMark = false;
  const out: JSX.Element[] = [];
  parts.forEach((part, i) => {
    if (part === "<mark>") inMark = true;
    else if (part === "</mark>") inMark = false;
    else if (part) out.push(inMark ? <mark key={i}>{part}</mark> : <Fragment key={i}>{part}</Fragment>);
  });
  return <>{out}</>;
}

export function Linkified({ body }: { body: string }) {
  return (
    <>
      {splitReportNos(body).map((part, i) =>
        part.kind === "text" ? <Fragment key={i}>{part.text}</Fragment> : <ReportLink key={i} reportNo={part.reportNo} />,
      )}
    </>
  );
}

export function termPattern(terms: string[]): RegExp {
  const escaped = terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  return new RegExp(`(?<![\\p{L}\\p{N}_])(${escaped.join("|")})(?![\\p{L}\\p{N}_])`, "giu");
}

export function Highlighted({ text, terms }: { text: string; terms: string[] }) {
  const usable = terms.map((t) => t.trim()).filter((t) => t.length >= 3);
  if (usable.length === 0) return <>{text}</>;
  const re = termPattern(usable);
  const out: JSX.Element[] = [];
  let last = 0;
  for (const m of text.matchAll(re)) {
    const start = m.index ?? 0;
    if (start > last) out.push(<Fragment key={`t${last}`}>{text.slice(last, start)}</Fragment>);
    out.push(<mark key={`m${start}`} className="term-mark">{m[0]}</mark>);
    last = start + m[0].length;
  }
  if (last < text.length) out.push(<Fragment key={`t${last}`}>{text.slice(last)}</Fragment>);
  return <>{out}</>;
}

export function fmtTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${d.toISOString().slice(0, 16).replace("T", " ")} UTC`;
}

export function fmtCount(n: number): string {
  return n.toLocaleString("en-US");
}

export function shortHash(sha: string): string {
  return sha.slice(0, 12);
}
