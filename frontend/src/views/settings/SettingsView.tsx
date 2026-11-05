import { Button, Callout, FormGroup, HTMLSelect, InputGroup, NonIdealState, Spinner } from "@blueprintjs/core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../api/client";
import { useSession } from "../../session/SessionProvider";

export function SettingsView() {
  const { isLead } = useSession();
  const client = useQueryClient();
  const settings = useQuery({ queryKey: ["opencode-go"], queryFn: api.goSettings });
  const models = useQuery({ queryKey: ["opencode-go-models"], queryFn: api.goModels, enabled: isLead });
  const [key, setKey] = useState("");
  const [model, setModel] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: api.saveGoSettings,
    onSuccess: (data) => { setKey(""); setModel(null); client.setQueryData(["opencode-go"], data); },
  });
  if (settings.isPending) return <NonIdealState icon={<Spinner />} title="Loading settings" />;
  if (settings.isError) return <NonIdealState title="Settings unavailable" description={settings.error.message} />;
  const data = settings.data;
  const selected = model ?? data.model;
  return <div className="settings-view">
    <h2>Settings</h2>
    <h3>OpenCode Go</h3>
    <p>AI hazard classification sends public report narratives to OpenCode Go. Results are AI-generated inferences with verified evidence quotes.</p>
    <p>{data.configured ? `Key configured · ending in ${data.key_hint}` : "No API key configured"}</p>
    {data.updated_by && <p className="muted">Updated by {data.updated_by.display_name} · {data.updated_at}</p>}
    {isLead ? <form onSubmit={(event) => { event.preventDefault(); save.mutate({ ...(key ? { api_key: key } : {}), ...(selected !== data.model ? { model: selected } : {}) }); }}>
      <FormGroup label="API key" labelFor="go-key" helperText="Stored on the server. Leave blank to keep the current key.">
        <InputGroup id="go-key" type="password" autoComplete="off" value={key} onChange={(event) => setKey(event.currentTarget.value)} placeholder={data.key_hint ? `Ending in ${data.key_hint}` : "Paste an OpenCode Go key"} />
      </FormGroup>
      <FormGroup label="Model" labelFor="go-model">
        <HTMLSelect id="go-model" value={selected} onChange={(event) => setModel(event.currentTarget.value)} disabled={models.isPending}>
          {Array.from(new Set([selected, ...(models.data ?? [])])).map((id) => <option key={id} value={id}>{id}</option>)}
        </HTMLSelect>
      </FormGroup>
      {models.isError && <Callout intent="warning">Could not load models. {models.error.message}</Callout>}
      <div className="settings-actions">
        <Button type="submit" intent="primary" loading={save.isPending}>Save</Button>
        <Button disabled={!data.configured || save.isPending} onClick={() => save.mutate({ api_key: "" })}>Clear key</Button>
      </div>
    </form> : <p>Model · {data.model}. Only leads can change these settings.</p>}
    {save.isError && <Callout intent="danger">{save.error.message}</Callout>}
    {save.isSuccess && <Callout intent="success">Settings saved.</Callout>}
  </div>;
}
