import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

interface SelectionValue {
  selected: string[];
  isSelected: (reportNo: string) => boolean;
  toggle: (reportNo: string) => void;
  setMany: (reportNos: string[], on: boolean) => void;
  clear: () => void;
}

const SelectionContext = createContext<SelectionValue | null>(null);

export function useSelection(): SelectionValue {
  const value = useContext(SelectionContext);
  if (!value) throw new Error("useSelection outside SelectionProvider");
  return value;
}

export function SelectionProvider({ children }: { children: ReactNode }) {
  const [selected, setSelected] = useState<string[]>([]);
  const set = useMemo(() => new Set(selected), [selected]);

  const toggle = useCallback((reportNo: string) => {
    setSelected((cur) => (cur.includes(reportNo) ? cur.filter((r) => r !== reportNo) : [...cur, reportNo]));
  }, []);
  const setMany = useCallback((reportNos: string[], on: boolean) => {
    setSelected((cur) => {
      if (!on) return cur.filter((r) => !reportNos.includes(r));
      const add = reportNos.filter((r) => !cur.includes(r));
      return [...cur, ...add];
    });
  }, []);
  const clear = useCallback(() => setSelected([]), []);

  const value = useMemo(() => ({
    selected, isSelected: (r: string) => set.has(r), toggle, setMany, clear,
  }), [selected, set, toggle, setMany, clear]);

  return <SelectionContext.Provider value={value}>{children}</SelectionContext.Provider>;
}
