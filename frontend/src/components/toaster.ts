import { OverlayToaster, type ToastProps } from "@blueprintjs/core";
import { createRoot } from "react-dom/client";

const toaster = OverlayToaster.createAsync(
  { position: "bottom-right", maxToasts: 4 },
  { domRenderer: (element, container) => createRoot(container).render(element) },
);

export function toast(props: ToastProps): void {
  void toaster.then((t) => t.show({ timeout: 4000, ...props }));
}

export function toastError(e: unknown): void {
  toast({ intent: "danger", icon: "error", message: e instanceof Error ? e.message : String(e) });
}
