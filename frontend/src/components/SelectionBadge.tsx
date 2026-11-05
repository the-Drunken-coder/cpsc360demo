import { Button, ButtonGroup, Tooltip } from "@blueprintjs/core";
import { useNavigate } from "react-router-dom";
import { useSelection } from "../session/SelectionProvider";
import { useSession } from "../session/SessionProvider";
import { useInvestigate } from "./InvestigateProvider";

export function compareHref(reportNos: string[]): string {
  const params = new URLSearchParams();
  reportNos.forEach((r) => params.append("r", r));
  return `/compare?${params.toString()}`;
}

export function BulkActions({ reportNos, onClear, compact }: { reportNos: string[]; onClear?: () => void; compact?: boolean }) {
  const navigate = useNavigate();
  const investigate = useInvestigate();
  const { canWrite } = useSession();
  const n = reportNos.length;
  return (
    <ButtonGroup className="bulk-actions">
      <Tooltip content="Compare side by side (c)" disabled={n >= 2}>
        <Button small icon="comparison" text={compact ? undefined : "Compare"} disabled={n < 2}
          onClick={() => navigate(compareHref(reportNos))} />
      </Tooltip>
      <Tooltip content={canWrite ? "Add to investigation (i)" : "Read-only viewer"}>
        <Button small icon="folder-new" text={compact ? undefined : "Add to investigation"} disabled={n < 1 || !canWrite}
          onClick={() => investigate.open(reportNos)} />
      </Tooltip>
      {onClear && <Button small icon="cross" text={compact ? undefined : "Clear"} disabled={n < 1} onClick={onClear} />}
    </ButtonGroup>
  );
}

export function SelectionBadge() {
  const { selected, clear } = useSelection();
  if (selected.length === 0) return null;
  return (
    <div className="selection-badge">
      <span className="selection-count">{selected.length} selected</span>
      <BulkActions reportNos={selected} onClear={clear} compact />
    </div>
  );
}
