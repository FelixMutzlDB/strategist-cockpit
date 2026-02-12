import { useState } from "react";
import { StrategistCanvas } from "@/components/StrategistCanvas";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Card, CardContent } from "@/components/ui/card";
import { getCanvasSummary, type CanvasSummary } from "@/lib/api";
import { ExternalLink, Users, FileText, Loader2 } from "lucide-react";

export default function Canvas() {
  const [selectedActivity, setSelectedActivity] = useState<string | null>(null);
  const [summary, setSummary] = useState<CanvasSummary | null>(null);
  const [loading, setLoading] = useState(false);

  const handleBoxClick = async (activityId: string, label: string) => {
    setSelectedActivity(label);
    setLoading(true);
    try {
      const data = await getCanvasSummary(activityId);
      setSummary(data);
    } catch {
      setSummary(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Strategist Canvas</h1>
        <p className="text-muted-foreground mt-1">
          Click any box to explore related engagements, materials, and impact metrics.
        </p>
      </div>

      <StrategistCanvas onBoxClick={handleBoxClick} />

      <Dialog
        open={!!selectedActivity}
        onOpenChange={(open) => {
          if (!open) {
            setSelectedActivity(null);
            setSummary(null);
          }
        }}
      >
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{selectedActivity}</DialogTitle>
            <DialogDescription>
              Engagement summary and related materials
            </DialogDescription>
          </DialogHeader>

          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : summary ? (
            <div className="space-y-4">
              {/* Stats */}
              <div className="grid grid-cols-2 gap-3">
                <Card>
                  <CardContent className="p-4 flex items-center gap-3">
                    <FileText className="h-5 w-5 text-primary" />
                    <div>
                      <p className="text-2xl font-bold">{summary.engagement_count}</p>
                      <p className="text-xs text-muted-foreground">Engagements</p>
                    </div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-4 flex items-center gap-3">
                    <Users className="h-5 w-5 text-primary" />
                    <div>
                      <p className="text-2xl font-bold">{summary.accounts.length}</p>
                      <p className="text-xs text-muted-foreground">Accounts</p>
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Accounts */}
              {summary.accounts.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium mb-2">Accounts Touched</h4>
                  <div className="flex flex-wrap gap-1.5">
                    {summary.accounts.map((acct) => (
                      <span
                        key={acct}
                        className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium"
                      >
                        {acct}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Recent Engagements */}
              {summary.recent_engagements.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium mb-2">Recent Engagements</h4>
                  <div className="space-y-2">
                    {summary.recent_engagements.map((eng) => (
                      <div
                        key={eng.id}
                        className="rounded-lg border p-3 text-sm space-y-1"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-medium">{eng.customer}</span>
                          <span
                            className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                              eng.status === "Completed"
                                ? "bg-emerald-100 text-emerald-700"
                                : eng.status === "Ongoing"
                                ? "bg-blue-100 text-blue-700"
                                : "bg-gray-100 text-gray-700"
                            }`}
                          >
                            {eng.status}
                          </span>
                        </div>
                        {eng.engagement_title && (
                          <p className="text-muted-foreground">{eng.engagement_title}</p>
                        )}
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          {eng.fy && <span>{eng.fy}</span>}
                          {eng.engagement_type && (
                            <span className="border-l pl-2">{eng.engagement_type}</span>
                          )}
                          {eng.asq_url && (
                            <a
                              href={eng.asq_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="border-l pl-2 text-primary hover:underline inline-flex items-center gap-1"
                            >
                              ASQ <ExternalLink className="h-3 w-3" />
                            </a>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {summary.engagement_count === 0 && (
                <p className="text-sm text-muted-foreground text-center py-4">
                  No engagements found for this activity area yet.
                </p>
              )}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground text-center py-4">
              Unable to load summary.
            </p>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
