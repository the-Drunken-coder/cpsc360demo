import type { SavedSearch } from "../../api/types";
import { explorerHref } from "../../domain/filters";

export function savedSearchHref(search: SavedSearch): string {
  const { sort, ...filters } = search.query;
  return explorerHref(filters, { sort });
}
