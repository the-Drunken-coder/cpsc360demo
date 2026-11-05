export const REPORT_NO_PATTERN = /\d{8}-[0-9A-F]{5}-\d+/g;

export function isReportNo(value: string): boolean {
  return new RegExp(`^${REPORT_NO_PATTERN.source}$`).test(value.trim());
}

export type TextPart = { kind: "text"; text: string } | { kind: "report"; reportNo: string };

export function splitReportNos(body: string): TextPart[] {
  const parts: TextPart[] = [];
  let last = 0;
  for (const match of body.matchAll(REPORT_NO_PATTERN)) {
    const start = match.index ?? 0;
    if (start > last) parts.push({ kind: "text", text: body.slice(last, start) });
    parts.push({ kind: "report", reportNo: match[0] });
    last = start + match[0].length;
  }
  if (last < body.length) parts.push({ kind: "text", text: body.slice(last) });
  return parts;
}
