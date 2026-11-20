import { Button, Popover } from "@blueprintjs/core";
import { useId, useState } from "react";

export function LabHelp({ label, text }: { label: string; text: string }) {
  const id = useId();
  const [open, setOpen] = useState(false);
  return <Popover placement="auto" minimal autoFocus={false} enforceFocus={false} isOpen={open}
    onInteraction={setOpen} content={<p id={id} className="lab-help-text">{text}</p>}>
    <Button type="button" minimal small icon="help" aria-label={`Help: ${label}`}
      aria-describedby={open ? id : undefined} onKeyDown={(event) => {
        if (event.key === "Escape" && open) {
          event.stopPropagation();
          setOpen(false);
        }
      }} />
  </Popover>;
}
