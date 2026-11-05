const LAST_EXPLORER_LOCATION = "cpsc360.lastExplorerLocation";

export function rememberExplorerLocation(pathname: string, search: string) {
  if (pathname !== "/") return;
  try {
    window.sessionStorage.setItem(LAST_EXPLORER_LOCATION, `/${search}`);
  } catch {
    // A blocked session store only loses the return-location preference.
  }
}

export function lastExplorerLocation(): string {
  try {
    const stored = window.sessionStorage.getItem(LAST_EXPLORER_LOCATION);
    if (!stored) return "/";
    const url = new URL(stored, window.location.origin);
    return url.pathname === "/" ? `${url.pathname}${url.search}` : "/";
  } catch {
    return "/";
  }
}
