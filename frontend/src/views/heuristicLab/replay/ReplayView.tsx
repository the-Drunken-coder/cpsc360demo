import { Button, Callout, Classes, Drawer, Spinner } from "@blueprintjs/core";
import { useQuery } from "@tanstack/react-query";
import { type FormEvent, useMemo, useRef, useState } from "react";
import { api } from "../../../api/client";
import type { LabReplayBounds } from "../../../api/heuristicLab";
import { score } from "../../../domain/replay";
import { useRegisteredHotkeys } from "../../../hotkeys/registry";
import { useSession } from "../../../session/SessionProvider";
import { PreviewPanel } from "../../explorer/PreviewPanel";
import { LabModes } from "../LabModes";
import { createRuleDraft, prepareTriage, TriageEditor, type RuleDraft } from "../TriageEditor";
import { FeedColumn, RecallLog, ReplayBar, RulesColumn, ScoreColumn } from "./ReplayPanels";
import { type AppliedRules, useReplayPlayer } from "./useReplayPlayer";
import "../heuristicLab.css";
import "./replay.css";

// "Narrative contains candle" is the common case, so a new rule starts there.
function newRule() {
  return createRuleDraft({ name: "", match: "all", action: { kind: "watchlist" },
    conditions: [{ kind: "text", field: "narrative", operator: "contains_any", value: "" }] });
}

export function ReplayView() {
  const { user } = useSession();
  const bounds = useQuery({ queryKey: ["heuristic-lab", "replay-bounds"], queryFn: api.labReplayBounds });
  return <div className="replay-page">
    <header className="replay-header">
      <h1>Heuristic Lab</h1>
      <LabModes />
    </header>
    {bounds.isPending && <Spinner size={24} />}
    {bounds.isError && <Callout intent="danger">{bounds.error.message}</Callout>}
    {bounds.data && <ReplayWorkspace key={user.id} bounds={bounds.data} />}
  </div>;
}

function openReport(id: string, tab = "") {
  window.open(`/incidents/${encodeURIComponent(id)}${tab}`, "_blank", "noopener");
}

function ReplayWorkspace({ bounds }: { bounds: LabReplayBounds }) {
  const [range, setRange] = useState({ start: bounds.start, end: bounds.end });
  const [rules, setRules] = useState<RuleDraft[]>([]);
  const [applied, setApplied] = useState<AppliedRules>({ epoch: 0, from: bounds.start, rules: [], ids: [] });
  const player = useReplayPlayer(range, applied);
  const { state } = player;
  const [cursorId, setCursorId] = useState<string | null>(null);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [editing, setEditing] = useState<{ drafts: RuleDraft[]; focus: number } | null>(null);
  const editor = useRef<HTMLFormElement>(null);
  const totals = useMemo(() => score(state), [state]);
  const started = state.day !== null;
  const cursor = state.feed.find((item) => item.report.id === cursorId) ?? state.feed[0];

  function restart(next: { start: string; end: string }) {
    setRange(next);
    player.reset(next);
    setApplied((current) => ({ ...current, epoch: current.epoch + 1, from: next.start }));
    setCursorId(null);
    setPreviewId(null);
  }

  function moveCursor(step: number) {
    if (!cursor) return;
    const index = state.feed.indexOf(cursor) + step;
    const next = state.feed[Math.min(Math.max(index, 0), state.feed.length - 1)];
    if (next) setCursorId(next.report.id);
  }

  function openPreview(id: string) {
    player.pause();
    setPreviewId(id);
  }

  function edit(drafts: RuleDraft[], focus: number) {
    player.pause();
    setEditing({ drafts, focus });
  }

  function apply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing) return;
    const invalid = event.currentTarget.querySelector<HTMLInputElement | HTMLSelectElement>("input:invalid, select:invalid");
    if (invalid) {
      const detail = invalid.closest("details");
      if (detail) detail.open = true;
      invalid.reportValidity();
      return;
    }
    const arrival = editing.drafts.filter((rule) => (rule.trigger ?? "arrival") === "arrival");
    const prepared = prepareTriage(arrival);
    if (!prepared) return;
    setRules(editing.drafts);
    setApplied((current) => ({ epoch: current.epoch + 1, from: player.upcoming ?? range.end, rules: prepared,
      ids: arrival.map((rule) => rule.draftId) }));
    setEditing(null);
  }

  useRegisteredHotkeys({
    playPause: () => (player.playing ? player.pause() : player.play()),
    next: () => moveCursor(1),
    prev: () => moveCursor(-1),
    flag: () => cursor && player.mark(cursor.report.id, "flagged"),
    dismiss: () => cursor && player.mark(cursor.report.id, "dismissed"),
    open: () => cursor && openPreview(cursor.report.id),
    close: () => setPreviewId(null),
  });

  return <div className="replay-frame">
    <ReplayBar range={range} bounds={bounds} day={state.day} upcoming={player.upcoming} started={started}
      playing={player.playing} finished={player.finished} buffering={player.buffering} speed={player.speed}
      outcomes={state.outcomes} onRange={restart} onReset={() => restart(range)} onPlay={player.play}
      onPause={player.pause} onSpeed={player.setSpeed} />
    {player.error && <Callout intent="danger" compact>{player.error.message}</Callout>}
    <div className="replay-cols">
      <RulesColumn rules={rules} counts={state.ruleCounts} unmatched={state.unmatched}
        appliesFrom={started && applied.from > range.start && applied.rules.length > 0 ? applied.from : null}
        onNew={() => edit([...rules, newRule()], rules.length)}
        onEdit={(index) => edit(rules, index)} />
      <FeedColumn day={state.day} feed={state.feed} marks={state.marks} cursorId={cursor?.report.id ?? null}
        onCursor={setCursorId} onOpen={openPreview} onMark={player.mark} />
      {previewId ? <PreviewPanel reportNo={previewId} onClose={() => setPreviewId(null)}
        onOpen={() => openReport(previewId)} onRelated={() => openReport(previewId, "/related")} />
        : <ScoreColumn score={totals} />}
    </div>
    <RecallLog outcomes={state.outcomes} onOpen={openPreview} />

    <Drawer isOpen={editing !== null} onClose={() => setEditing(null)} title="Replay rules" size="min(640px, 100vw)"
      onOpened={() => {
        const detail = editor.current?.querySelectorAll("details")[editing?.focus ?? -1];
        if (detail) {
          detail.open = true;
          detail.querySelector("input")?.focus();
        }
      }}>
      {editing && <form ref={editor} className="replay-rule-form" noValidate onSubmit={apply}>
        <div className={`${Classes.DRAWER_BODY} lab-rule-editor`}>
          <TriageEditor rules={editing.drafts} disabled={false} onChange={(drafts) => setEditing({ ...editing, drafts })} />
        </div>
        <div className={Classes.DRAWER_FOOTER}>
          <span className="replay-note">
            {started ? `Applies from ${player.upcoming ?? range.end}. Reports already shown keep their tags.` : "Applies from the replay start."}
          </span>
          <Button type="button" text="Cancel" onClick={() => setEditing(null)} />
          <Button type="submit" intent="primary" text="Apply" />
        </div>
      </form>}
    </Drawer>
  </div>;
}
