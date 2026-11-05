import { Classes, HTMLTable, NonIdealState, Spinner } from "@blueprintjs/core";
import { useQuery } from "@tanstack/react-query";
import { api, qk } from "../../api/client";
import { fmtTime } from "../../components/text";

function Json({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <span className={Classes.TEXT_MUTED}>—</span>;
  const text = JSON.stringify(value, null, 1);
  if (text.length <= 80) return <code className="audit-json">{text.replace(/\n\s*/g, " ")}</code>;
  return (
    <details>
      <summary className={Classes.TEXT_MUTED}>{text.length} chars</summary>
      <pre className="audit-json">{text}</pre>
    </details>
  );
}

export function AuditPanel({ id }: { id: number }) {
  const audit = useQuery({ queryKey: qk.audit(id), queryFn: () => api.audit(id) });
  if (audit.isPending) return <Spinner />;
  if (audit.isError) return <NonIdealState icon="error" description={audit.error.message} />;
  return (
    <HTMLTable compact striped className="full-width dense-table audit-table">
      <thead><tr><th>When</th><th>Actor</th><th>Action</th><th>Entity</th><th>Before</th><th>After</th></tr></thead>
      <tbody>
        {audit.data.map((a) => (
          <tr key={a.id}>
            <td className="nowrap">{fmtTime(a.at)}</td>
            <td className="nowrap">{a.actor.display_name}</td>
            <td className="mono">{a.action}</td>
            <td className="mono">{a.entity} {a.entity_id}</td>
            <td><Json value={a.before} /></td>
            <td><Json value={a.after} /></td>
          </tr>
        ))}
      </tbody>
    </HTMLTable>
  );
}
