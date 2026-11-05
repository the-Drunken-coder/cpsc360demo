import { Button, Callout } from "@blueprintjs/core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useSession } from "../session/SessionProvider";
import { toast } from "./toaster";

export function AIClassifyButton({ reportNos, bulk = false }: { reportNos: string[]; bulk?: boolean }) {
  const { canWrite } = useSession();
  const client = useQueryClient();
  const setting = useQuery({ queryKey: ["opencode-go"], queryFn: api.goSettings });
  const classify = useMutation({
    mutationFn: () => api.classifyHazards(reportNos),
    onSuccess: (results) => {
      const ok = results.filter((result) => result.status === "ok").length;
      toast({ intent: ok === results.length ? "success" : "warning", message: `AI hazards · ${ok} ok, ${results.length - ok} errors` });
      void client.invalidateQueries({ queryKey: ["incident"] });
    },
  });
  if (setting.isError) return <Callout intent="warning">{setting.error.message}</Callout>;
  if (setting.data && !setting.data.configured) return <Link to="/settings">Configure AI in Settings</Link>;
  if (!canWrite) return null;
  return <div>
    <Button small icon="predictive-analysis" loading={classify.isPending}
      disabled={!setting.data?.configured || reportNos.length < 1 || reportNos.length > 50}
      title="Select 1 to 50 reports" onClick={() => classify.mutate()}>
      {bulk ? "Classify hazards with AI" : "Classify with AI"}
    </Button>
    {classify.isError && <Callout intent="danger">{classify.error.message}</Callout>}
  </div>;
}
