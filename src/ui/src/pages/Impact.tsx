import { useEffect, useState } from "react";
import { ExternalLink, BarChart3, AlertCircle } from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { getAppConfig, type AppConfig } from "@/lib/api";

export default function Impact() {
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
    return <div className="text-muted-foreground">Loading dashboard…</div>;
  }
  if (error || !config) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-destructive" />
            Could not load dashboard config
          </CardTitle>
          <CardDescription>{error ?? "Unknown error"}</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const dashboardUrl =
    config.databricks_host && config.lakeview_dashboard_id
      ? `https://${config.databricks_host}/embed/dashboardsv3/${config.lakeview_dashboard_id}`
      : null;

  if (!dashboardUrl) {
    return (
      <Card>
        <CardHeader>
          <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-blue-500/10 to-indigo-500/10 flex items-center justify-center mb-2">
            <BarChart3 className="h-6 w-6 text-blue-600" />
          </div>
          <CardTitle>Impact Dashboard not configured</CardTitle>
          <CardDescription>
            Set <code>DATABRICKS_HOST</code> and <code>LAKEVIEW_DASHBOARD_ID</code> in
            <code> app.yaml</code> (prod) or <code>.env</code> (dev) to enable the
            embedded Lakeview dashboard here.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Impact Dashboard</h1>
          <p className="text-muted-foreground text-sm">
            Engagement impact, revenue lift, and territory comparisons.
          </p>
        </div>
        <Button variant="outline" size="sm" asChild>
          <a href={dashboardUrl} target="_blank" rel="noopener noreferrer">
            Open in Databricks
            <ExternalLink className="ml-2 h-4 w-4" />
          </a>
        </Button>
      </div>
      <div className="rounded-lg border overflow-hidden bg-background">
        <iframe
          src={dashboardUrl}
          title="Strategist Impact Dashboard"
          className="w-full border-0 h-[calc(100vh-220px)] min-h-[600px]"
        />
      </div>
    </div>
  );
}
