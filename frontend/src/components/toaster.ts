import { OverlayToaster, type ToastProps } from "@blueprintjs/core";

const toaster = OverlayToaster.createAsync({ position: "bottom-right", maxToasts: 4 });

export function toast(props: ToastProps): void {
  void toaster.then((t) => t.show({ timeout: 4000, ...props }));
}

export function toastError(e: unknown): void {
  toast({ intent: "danger", icon: "error", message: e instanceof Error ? e.message : String(e) });
}
