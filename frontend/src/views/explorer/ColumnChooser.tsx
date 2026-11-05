import { Button, Checkbox, Menu, MenuDivider, Popover } from "@blueprintjs/core";
import { useState } from "react";
import { COLUMNS } from "./columns";

const KEY = "cpsc360.columns";

function readColumns(): string[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      const ids = JSON.parse(raw) as unknown;
      if (Array.isArray(ids)) return ids.filter((id): id is string => typeof id === "string");
    }
  } catch {
    // Unreadable preference falls back to the default columns.
  }
  return COLUMNS.filter((c) => c.defaultVisible).map((c) => c.id);
}

export function useVisibleColumns() {
  const [visible, setVisible] = useState<string[]>(readColumns);
  const update = (ids: string[]) => {
    setVisible(ids);
    try {
      localStorage.setItem(KEY, JSON.stringify(ids));
    } catch {
      // Preference is per-tab when storage is blocked.
    }
  };
  return { columns: COLUMNS.filter((c) => visible.includes(c.id)), visible, setVisible: update };
}

export function ColumnChooser({ visible, onChange }: { visible: string[]; onChange: (ids: string[]) => void }) {
  return (
    <Popover placement="bottom-end" content={
      <Menu className="column-chooser">
        <MenuDivider title="Columns" />
        {COLUMNS.map((c) => (
          <li key={c.id} className="column-option">
            <Checkbox label={c.label} checked={visible.includes(c.id)}
              onChange={() => onChange(visible.includes(c.id) ? visible.filter((v) => v !== c.id) : [...visible, c.id])} />
          </li>
        ))}
        <MenuDivider />
        <li className="column-option">
          <Button minimal small text="Reset to default"
            onClick={() => onChange(COLUMNS.filter((c) => c.defaultVisible).map((c) => c.id))} />
        </li>
      </Menu>
    }>
      <Button small minimal icon="column-layout" text="Columns" />
    </Popover>
  );
}
