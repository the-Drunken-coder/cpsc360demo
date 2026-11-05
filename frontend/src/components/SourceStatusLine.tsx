import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, qk } from "../api/client";
import { fmtCount } from "./text";

export function SourceStatusLine() {
  const status = useQuery({ queryKey: qk.sourceStatus(), queryFn: api.sourceStatus, staleTime: 60_000 });
  if (!status.data) return null;
  const { incident_count, newest_report_date, newest_publication_date } = status.data;
  return (
    <Link to="/source" className="source-status-line" title="Ingest batches and sync">
      {fmtCount(incident_count)} public reports · newest submitted {newest_report_date} · published {newest_publication_date}
    </Link>
  );
}
