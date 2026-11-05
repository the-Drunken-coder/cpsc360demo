import { Classes, Dialog, DialogBody, HTMLTable, KeyComboTag, useHotkeys, type HotkeyConfig } from "@blueprintjs/core";
import { useMemo, useRef } from "react";

interface HotkeyDef { combo: string; label: string; group: "Global" | "Explorer" | "Selection" }

export const HOTKEYS = {
  omnibar: { combo: "mod+k", label: "Jump to a report, investigation, saved search, or view", group: "Global" },
  help: { combo: "?", label: "Show keyboard shortcuts", group: "Global" },
  focusSearch: { combo: "/", label: "Focus search", group: "Explorer" },
  next: { combo: "j", label: "Move row cursor down", group: "Explorer" },
  prev: { combo: "k", label: "Move row cursor up", group: "Explorer" },
  toggle: { combo: "x", label: "Toggle selection of the focused row", group: "Explorer" },
  open: { combo: "enter", label: "Open the focused report", group: "Explorer" },
  close: { combo: "esc", label: "Close the preview panel", group: "Explorer" },
  compare: { combo: "c", label: "Compare selected reports", group: "Selection" },
  investigate: { combo: "i", label: "Add selection to an investigation", group: "Explorer" },
  related: { combo: "r", label: "Related reports for the focused report", group: "Explorer" },
} as const satisfies Record<string, HotkeyDef>;

export type HotkeyId = keyof typeof HOTKEYS;
export type HotkeyHandlers = Partial<Record<HotkeyId, () => void>>;

export function useRegisteredHotkeys(handlers: HotkeyHandlers) {
  const ref = useRef(handlers);
  ref.current = handlers;
  const ids = (Object.keys(handlers) as HotkeyId[]).sort().join(",");
  const configs = useMemo<HotkeyConfig[]>(
    () => (ids ? (ids.split(",") as HotkeyId[]) : [])
      .filter((id) => id !== "help")
      .map((id) => ({
        ...HOTKEYS[id],
        global: true,
        preventDefault: id !== "open" && id !== "compare",
        onKeyDown: (event: KeyboardEvent) => {
          if (document.querySelector("[role=dialog], .bp5-omnibar")) return;
          if (id === "compare") {
            if (event.target instanceof Element && event.target.closest("select")) return;
            event.preventDefault();
          }
          // Enter on a link, button, or select must keep its native action.
          if (id === "open") {
            if ((event.target as HTMLElement | null)?.closest("a, button, select, [role=button]")) return;
            event.preventDefault();
          }
          ref.current[id]?.();
        },
      })),
    [ids],
  );
  return useHotkeys(configs, { showDialogKeyCombo: HOTKEYS.help.combo });
}

export function HotkeysHelp({ active, onClose }: { active: HotkeyConfig[]; onClose: () => void }) {
  const activeCombos = new Set(active.map((h) => h.combo));
  const groups = ["Global", "Explorer", "Selection"] as const;
  return (
    <Dialog isOpen onClose={onClose} title="Keyboard shortcuts" icon="key-command" className="hotkeys-help">
      <DialogBody>
        {groups.map((group) => (
          <section key={group}>
            <h4 className={Classes.HEADING}>{group}</h4>
            <HTMLTable compact className="full-width">
              <tbody>
                {Object.values(HOTKEYS).filter((h) => h.group === group).map((h) => (
                  <tr key={h.combo} className={activeCombos.has(h.combo) || h.combo === "?" ? "" : Classes.TEXT_DISABLED}>
                    <td className="hotkey-combo"><KeyComboTag combo={h.combo} /></td>
                    <td>{h.label}</td>
                  </tr>
                ))}
              </tbody>
            </HTMLTable>
          </section>
        ))}
        <p className={Classes.TEXT_MUTED}>Dimmed shortcuts are not active in the current view.</p>
      </DialogBody>
    </Dialog>
  );
}
