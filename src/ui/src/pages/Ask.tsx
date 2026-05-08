import { useEffect, useState } from "react";
import { ExternalLink, MessageSquare, AlertCircle } from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { getAppConfig, type AppConfig } from "@/lib/api";

export default function Ask() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAppConfig()
      .then(setConfig)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="text-muted-foreground">Loading Genie space…</div>;
  }
  if (error || !config) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-destructive" />
            Could not load Genie config
          </CardTitle>
          <CardDescription>{error ?? "Unknown error"}</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const genieEmbedUrl =
    config.databricks_host && config.genie_space_id
      ? `https://${config.databricks_host}/embed/genie/${config.genie_space_id}`
      : null;
  const genieDeepLinkUrl =
    config.databricks_host && config.genie_space_id
      ? `https://${config.databricks_host}/genie/rooms/${config.genie_space_id}`
      : null;

  if (!genieEmbedUrl) {
    return (
      <Card>
        <CardHeader>
          <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-indigo-500/10 to-purple-500/10 flex items-center justify-center mb-2">
            <MessageSquare className="h-6 w-6 text-indigo-600" />
          </div>
          <CardTitle>Ask the data — not yet configured</CardTitle>
          <CardDescription>
            Set <code>DATABRICKS_HOST</code> and <code>GENIE_SPACE_ID</code> in
            <code> app.yaml</code> (prod) or <code>.env</code> (dev) to enable
            the embedded Strategist Cockpit Genie here.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Ask the Data</h1>
          <p className="text-muted-foreground text-sm">
            Natural-language Q&amp;A over your engagements + revenue, powered by
            the Strategist Cockpit Genie.
          </p>
        </div>
        {genieDeepLinkUrl && (
          <Button variant="outline" size="sm" asChild>
            <a href={genieDeepLinkUrl} target="_blank" rel="noopener noreferrer">
              Open in Databricks
              <ExternalLink className="ml-2 h-4 w-4" />
            </a>
          </Button>
        )}
      </div>
      <div className="rounded-lg border overflow-hidden bg-background">
        <iframe
          src={genieEmbedUrl}
          title="Strategist Cockpit Genie"
          className="w-full border-0 h-[calc(100vh-220px)] min-h-[600px]"
        />
      </div>
    </div>
  );
}
