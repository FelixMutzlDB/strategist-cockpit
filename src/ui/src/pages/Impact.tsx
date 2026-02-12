import { useState, useEffect } from "react";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { listEngagements, type Engagement } from "@/lib/api";
import { BarChart3, Users, Target, CheckCircle, ExternalLink, Filter } from "lucide-react";

const FY_OPTIONS = ["FY25", "FY26", "FY27"];
const TYPE_OPTIONS = ["Focus", "One-off", "Customer Event"];
const STATUS_OPTIONS = ["Completed", "Ongoing", "Abandoned", "Not started", "On hold"];

export default function Impact() {
  const [engagements, setEngagements] = useState<Engagement[]>([]);
  const [filteredEngagements, setFilteredEngagements] = useState<Engagement[]>([]);
  const [fyFilter, setFyFilter] = useState<string>("");
  const [typeFilter, setTypeFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadEngagements();
  }, []);

  useEffect(() => {
    let filtered = engagements;
    if (fyFilter) filtered = filtered.filter((e) => e.fy === fyFilter);
    if (typeFilter) filtered = filtered.filter((e) => e.engagement_type === typeFilter);
    if (statusFilter) filtered = filtered.filter((e) => e.status === statusFilter);
    setFilteredEngagements(filtered);
  }, [engagements, fyFilter, typeFilter, statusFilter]);

  const loadEngagements = async () => {
    try {
      const data = await listEngagements();
      setEngagements(data);
    } catch (e) {
      console.error("Failed to load engagements:", e);
    } finally {
      setLoading(false);
    }
  };

  const totalEngagements = filteredEngagements.length;
  const focusAccounts = new Set(
    filteredEngagements.filter((e) => e.engagement_type === "Focus").map((e) => e.customer)
  ).size;
  const completedCount = filteredEngagements.filter((e) => e.status === "Completed").length;
  const ongoingCount = filteredEngagements.filter((e) => e.status === "Ongoing").length;

  // Aggregate by quarter
  const quarterCounts: Record<string, number> = {};
  filteredEngagements.forEach((e) => {
    if (e.quarter) {
      // quarter can be multi-valued like "FY25Q3, FY25Q4"
      const quarters = e.quarter.split(",").map((q) => q.trim());
      quarters.forEach((q) => {
        quarterCounts[q] = (quarterCounts[q] || 0) + 1;
      });
    }
  });
  const sortedQuarters = Object.entries(quarterCounts).sort(([a], [b]) => a.localeCompare(b));
  const maxQuarterCount = Math.max(...Object.values(quarterCounts), 1);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Impact Dashboard</h1>
        <p className="text-muted-foreground mt-1">
          Track engagements over time with filters for fiscal year, type, and status.
        </p>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium">Filters:</span>
            </div>

            <select
              value={fyFilter}
              onChange={(e) => setFyFilter(e.target.value)}
              className="rounded-md border bg-background px-3 py-1.5 text-sm"
            >
              <option value="">All FY</option>
              {FY_OPTIONS.map((fy) => (
                <option key={fy} value={fy}>
                  {fy}
                </option>
              ))}
            </select>

            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="rounded-md border bg-background px-3 py-1.5 text-sm"
            >
              <option value="">All Types</option>
              {TYPE_OPTIONS.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>

            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-md border bg-background px-3 py-1.5 text-sm"
            >
              <option value="">All Status</option>
              {STATUS_OPTIONS.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>

            {(fyFilter || typeFilter || statusFilter) && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setFyFilter("");
                  setTypeFilter("");
                  setStatusFilter("");
                }}
              >
                Clear all
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* KPI Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-blue-100 flex items-center justify-center">
              <BarChart3 className="h-5 w-5 text-blue-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">{totalEngagements}</p>
              <p className="text-xs text-muted-foreground">Total Engagements</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-purple-100 flex items-center justify-center">
              <Target className="h-5 w-5 text-purple-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">{focusAccounts}</p>
              <p className="text-xs text-muted-foreground">Focus Accounts</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-emerald-100 flex items-center justify-center">
              <CheckCircle className="h-5 w-5 text-emerald-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">{completedCount}</p>
              <p className="text-xs text-muted-foreground">Completed</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-amber-100 flex items-center justify-center">
              <Users className="h-5 w-5 text-amber-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">{ongoingCount}</p>
              <p className="text-xs text-muted-foreground">Ongoing</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Quarter Bar Chart */}
      {sortedQuarters.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Engagements by Quarter</CardTitle>
            <CardDescription>Distribution across fiscal quarters</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {sortedQuarters.map(([quarter, count]) => (
                <div key={quarter} className="flex items-center gap-3">
                  <span className="text-xs font-mono w-20 text-right text-muted-foreground">
                    {quarter}
                  </span>
                  <div className="flex-1 h-6 bg-muted rounded-md overflow-hidden">
                    <div
                      className="h-full bg-primary/80 rounded-md transition-all"
                      style={{ width: `${(count / maxQuarterCount) * 100}%` }}
                    />
                  </div>
                  <span className="text-xs font-medium w-6 text-right">{count}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Engagement Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Engagement Details</CardTitle>
          <CardDescription>
            {filteredEngagements.length} engagement{filteredEngagements.length !== 1 && "s"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-muted-foreground text-sm">Loading...</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left">
                    <th className="pb-2 font-medium">Customer</th>
                    <th className="pb-2 font-medium">Title</th>
                    <th className="pb-2 font-medium">Type</th>
                    <th className="pb-2 font-medium">Status</th>
                    <th className="pb-2 font-medium">FY</th>
                    <th className="pb-2 font-medium">AE</th>
                    <th className="pb-2 font-medium">ASQ</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredEngagements.map((eng) => (
                    <tr key={eng.id} className="border-b last:border-0 hover:bg-muted/50">
                      <td className="py-2 font-medium">{eng.customer}</td>
                      <td className="py-2 text-muted-foreground max-w-[200px] truncate">
                        {eng.engagement_title || "--"}
                      </td>
                      <td className="py-2">
                        <span
                          className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                            eng.engagement_type === "Focus"
                              ? "bg-purple-100 text-purple-700"
                              : eng.engagement_type === "One-off"
                              ? "bg-blue-100 text-blue-700"
                              : eng.engagement_type === "Customer Event"
                              ? "bg-amber-100 text-amber-700"
                              : "bg-gray-100 text-gray-700"
                          }`}
                        >
                          {eng.engagement_type || "--"}
                        </span>
                      </td>
                      <td className="py-2">
                        <span
                          className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                            eng.status === "Completed"
                              ? "bg-emerald-100 text-emerald-700"
                              : eng.status === "Ongoing"
                              ? "bg-blue-100 text-blue-700"
                              : eng.status === "Abandoned"
                              ? "bg-red-100 text-red-700"
                              : "bg-gray-100 text-gray-700"
                          }`}
                        >
                          {eng.status || "--"}
                        </span>
                      </td>
                      <td className="py-2 text-muted-foreground">{eng.fy || "--"}</td>
                      <td className="py-2 text-muted-foreground">{eng.ae || "--"}</td>
                      <td className="py-2">
                        {eng.asq_url ? (
                          <a
                            href={eng.asq_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-primary hover:underline inline-flex items-center gap-1"
                          >
                            View <ExternalLink className="h-3 w-3" />
                          </a>
                        ) : (
                          <span className="text-muted-foreground">--</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
