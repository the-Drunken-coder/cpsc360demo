import { Button, Classes, Dialog, DialogBody, DialogFooter, Icon, InputGroup, Tag, Tooltip } from "@blueprintjs/core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, qk } from "../../api/client";
import type { Filters } from "../../api/types";
import { toast, toastError } from "../../components/toaster";
import { filtersEqual, isEmptyFilters } from "../../domain/filters";
import { useSession } from "../../session/SessionProvider";
import { savedSearchHref } from "./savedSearch";

export function SavedSearches({ filters, sort }: { filters: Filters; sort: string }) {
  const { user, canWrite } = useSession();
  const queryClient = useQueryClient();
  const saved = useQuery({ queryKey: qk.savedSearches(), queryFn: api.savedSearches });
  const [naming, setNaming] = useState(false);
  const [name, setName] = useState("");

  const create = useMutation({
    mutationFn: () => api.createSavedSearch(name.trim(), { ...filters, sort }),
    onSuccess: (s) => {
      void queryClient.invalidateQueries({ queryKey: qk.savedSearches() });
      toast({ intent: "success", icon: "bookmark", message: `Saved “${s.name}”.` });
      setNaming(false);
      setName("");
    },
    onError: toastError,
  });
  const remove = useMutation({
    mutationFn: (id: number) => api.deleteSavedSearch(id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: qk.savedSearches() }),
    onError: toastError,
  });

  return (
    <section className="facet saved-searches">
      <div className="facet-title">
        Saved searches
        <Tooltip content={canWrite ? "Save the current filters" : "Read-only viewer"}>
          <Button minimal small icon="add" disabled={!canWrite || isEmptyFilters(filters)} onClick={() => setNaming(true)}
            aria-label="Save current search" />
        </Tooltip>
      </div>
      {saved.data?.length === 0 && <div className={`${Classes.TEXT_MUTED} facet-note`}>None yet.</div>}
      {saved.data?.map((s) => {
        const { sort: _sort, ...query } = s.query;
        const current = filtersEqual(query, filters);
        return (
          <div key={s.id} className={`saved-search ${current ? "current" : ""}`}>
            <Link to={savedSearchHref(s)} title={`Owner: ${s.owner.display_name}`}>
              <Icon icon={current ? "tick" : "bookmark"} size={12} /> {s.name}
            </Link>
            {s.shared && <Tag minimal className="saved-shared">shared</Tag>}
            {s.owner.id === user.id && canWrite && (
              <Button minimal small icon="trash" aria-label={`Delete ${s.name}`} onClick={() => remove.mutate(s.id)} />
            )}
          </div>
        );
      })}
      <Dialog isOpen={naming} onClose={() => setNaming(false)} title="Save search" icon="bookmark">
        <DialogBody>
          <InputGroup autoFocus placeholder="Name" value={name} onChange={(e) => setName(e.currentTarget.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && name.trim()) create.mutate(); }} />
          <p className={`${Classes.TEXT_MUTED} saved-hint`}>Saves the filters and sort currently in the URL.</p>
        </DialogBody>
        <DialogFooter actions={<>
          <Button text="Cancel" onClick={() => setNaming(false)} />
          <Button intent="primary" text="Save" disabled={!name.trim()} loading={create.isPending} onClick={() => create.mutate()} />
        </>} />
      </Dialog>
    </section>
  );
}
