import { MenuItem, type IconName } from "@blueprintjs/core";
import { Omnibar } from "@blueprintjs/select";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api, qk } from "../api/client";
import type { InvestigationSummaryRow, SavedSearch } from "../api/types";
import { explorerHref } from "../domain/filters";
import { isReportNo } from "../domain/reportNo";
import { savedSearchHref } from "../views/explorer/savedSearch";

type Item =
  | { kind: "view"; label: string; to: string; icon: IconName }
  | { kind: "report"; reportNo: string }
  | { kind: "search"; q: string }
  | { kind: "investigation"; row: InvestigationSummaryRow }
  | { kind: "saved"; search: SavedSearch };

const VIEWS: Item[] = [
  { kind: "view", label: "Explorer", to: "/", icon: "search-template" },
  { kind: "view", label: "Analytics", to: "/analytics", icon: "timeline-bar-chart" },
  { kind: "view", label: "Investigations", to: "/investigations", icon: "folder-shared" },
  { kind: "view", label: "Source and sync status", to: "/source", icon: "database" },
];

function itemKey(item: Item): string {
  switch (item.kind) {
    case "view": return `view:${item.to}`;
    case "report": return `report:${item.reportNo}`;
    case "search": return `search:${item.q}`;
    case "investigation": return `inv:${item.row.id}`;
    case "saved": return `saved:${item.search.id}`;
  }
}

function itemHref(item: Item): string {
  switch (item.kind) {
    case "view": return item.to;
    case "report": return `/incidents/${item.reportNo}`;
    case "search": return explorerHref({ q: item.q });
    case "investigation": return `/investigations/${item.row.id}`;
    case "saved": return savedSearchHref(item.search);
  }
}

function itemView(item: Item): { text: string; icon: IconName; label: string } {
  switch (item.kind) {
    case "view": return { text: item.label, icon: item.icon, label: "View" };
    case "report": return { text: `Open report ${item.reportNo}`, icon: "document-open", label: "Report" };
    case "search": return { text: `Search reports for “${item.q}”`, icon: "search", label: "Full text" };
    case "investigation":
      return { text: `#${item.row.id} ${item.row.title}`, icon: "folder-close", label: `${item.row.incident_count} reports` };
    case "saved": return { text: item.search.name, icon: "bookmark", label: item.search.shared ? "Shared search" : "Saved search" };
  }
}

const matches = (text: string, q: string) => text.toLowerCase().includes(q.toLowerCase());

export function AppOmnibar({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const investigations = useQuery({ queryKey: qk.investigations(), queryFn: () => api.investigations(), enabled: isOpen });
  const saved = useQuery({ queryKey: qk.savedSearches(), queryFn: api.savedSearches, enabled: isOpen });

  const items: Item[] = [
    ...VIEWS,
    ...(investigations.data ?? []).map((row): Item => ({ kind: "investigation", row })),
    ...(saved.data ?? []).map((search): Item => ({ kind: "saved", search })),
  ];

  return (
    <Omnibar<Item>
      isOpen={isOpen}
      onClose={onClose}
      items={items}
      resetOnSelect
      inputProps={{ placeholder: "Report number, investigation, saved search, view, or search text…" }}
      itemListPredicate={(query, all) => {
        const q = query.trim();
        if (!q) return all;
        const found = all.filter((item) => {
          if (item.kind === "investigation") return matches(`#${item.row.id} ${item.row.title} ${item.row.labels.join(" ")}`, q);
          if (item.kind === "saved") return matches(item.search.name, q);
          if (item.kind === "view") return matches(item.label, q);
          return false;
        });
        const upper = q.toUpperCase();
        const report: Item[] = isReportNo(upper) ? [{ kind: "report", reportNo: upper }] : [];
        return [...report, ...found, { kind: "search", q }];
      }}
      itemRenderer={(item, { handleClick, modifiers }) => {
        if (!modifiers.matchesPredicate) return null;
        const v = itemView(item);
        return <MenuItem key={itemKey(item)} active={modifiers.active} icon={v.icon} text={v.text} label={v.label}
          onClick={handleClick} />;
      }}
      onItemSelect={(item) => {
        onClose();
        navigate(itemHref(item));
      }}
    />
  );
}
