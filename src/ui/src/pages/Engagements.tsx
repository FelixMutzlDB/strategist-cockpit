import { useState, useEffect, useMemo } from "react";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  listEngagements,
  createEngagement,
  updateEngagement,
  deleteEngagement,
  type Engagement,
} from "@/lib/api";
import {
  BarChart3,
  Users,
  Target,
  CheckCircle,
  ExternalLink,
  Filter,
  Plus,
  Pencil,
  Trash2,
  Save,
  X,
  Eye,
  ArrowUp,
  ArrowDown,
  ArrowUpDown,
  Search,
} from "lucide-react";

const ENGAGEMENT_TYPES = ["Focus", "One-off", "Customer Event", "Tbc"];
const STATUS_OPTIONS = ["Completed", "Ongoing", "Abandoned", "Not started", "On hold"];
const FY_OPTIONS = ["FY25", "FY26", "FY27", "FY28"];

const EMPTY_FORM: Omit<Engagement, "id"> = {
  customer: "",
  engagement_title: "",
  engagement_type: null,
  status: null,
  actionable_outcome: null,
  ae: null,
  asq_url: null,
  asq_id: null,
  timeframe: null,
  fy: null,
  quarter: null,
  related_documents: null,
  next_steps: null,
  uco_ids: null,
};

type SortDir = "asc" | "desc" | null;
type SortKey = keyof Engagement;

interface ColumnFilter {
  customer: string;
  engagement_title: string;
  engagement_type: string;
  status: string;
  fy: string;
  quarter: string;
  ae: string;
  asq_id: string;
}

const EMPTY_COL_FILTERS: ColumnFilter = {
  customer: "",
  engagement_title: "",
  engagement_type: "",
  status: "",
  fy: "",
  quarter: "",
  ae: "",
  asq_id: "",
};

function typeBadge(val: string | null) {
  const cls =
    val === "Focus"
      ? "bg-purple-100 text-purple-700"
      : val === "One-off"
      ? "bg-blue-100 text-blue-700"
      : val === "Customer Event"
      ? "bg-amber-100 text-amber-700"
      : "bg-gray-100 text-gray-700";
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>
      {val || "--"}
    </span>
  );
}

function statusBadge(val: string | null) {
  const cls =
    val === "Completed"
      ? "bg-emerald-100 text-emerald-700"
      : val === "Ongoing"
      ? "bg-blue-100 text-blue-700"
      : val === "Abandoned"
      ? "bg-red-100 text-red-700"
      : "bg-gray-100 text-gray-700";
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>
      {val || "--"}
    </span>
  );
}

export default function Engagements() {
  const [engagements, setEngagements] = useState<Engagement[]>([]);
  const [loading, setLoading] = useState(true);

  // Global text search
  const [searchQuery, setSearchQuery] = useState("");
  // Top-level dropdown filters
  const [fyFilter, setFyFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  // Per-column filters
  const [colFilters, setColFilters] = useState<ColumnFilter>(EMPTY_COL_FILTERS);
  // Sort state
  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>(null);

  // Dialogs
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [viewingEng, setViewingEng] = useState<Engagement | null>(null);
  const [form, setForm] = useState<Omit<Engagement, "id">>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);

  useEffect(() => {
    loadEngagements();
  }, []);

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

  // Combined filtering pipeline: global search -> top-level dropdowns -> per-column filters
  const filteredEngagements = useMemo(() => {
    let result = engagements;

    // Global text search across all fields
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      result = result.filter((e) => {
        const haystack = [
          e.customer,
          e.engagement_title,
          e.engagement_type,
          e.status,
          e.fy,
          e.quarter,
          e.ae,
          e.asq_id,
          e.actionable_outcome,
          e.next_steps,
          e.timeframe,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        return haystack.includes(q);
      });
    }

    // Top-level dropdown filters
    if (fyFilter) result = result.filter((e) => e.fy === fyFilter);
    if (typeFilter) result = result.filter((e) => e.engagement_type === typeFilter);
    if (statusFilter) result = result.filter((e) => e.status === statusFilter);

    // Per-column filters
    const getField = (e: Engagement, key: string): string | null =>
      (e as unknown as Record<string, string | null>)[key];

    for (const [key, val] of Object.entries(colFilters)) {
      if (val) {
        const v = val.toLowerCase();
        result = result.filter((e) => {
          const cell = getField(e, key);
          return typeof cell === "string" && cell.toLowerCase().includes(v);
        });
      }
    }

    // Sorting
    if (sortKey && sortDir) {
      result = [...result].sort((a, b) => {
        const aVal = getField(a, sortKey) ?? "";
        const bVal = getField(b, sortKey) ?? "";
        const cmp = String(aVal).localeCompare(String(bVal), undefined, { numeric: true });
        return sortDir === "asc" ? cmp : -cmp;
      });
    }

    return result;
  }, [engagements, searchQuery, fyFilter, typeFilter, statusFilter, colFilters, sortKey, sortDir]);

  // KPI computations
  const totalEngagements = filteredEngagements.length;
  const focusAccounts = new Set(
    filteredEngagements.filter((e) => e.engagement_type === "Focus").map((e) => e.customer)
  ).size;
  const completedCount = filteredEngagements.filter((e) => e.status === "Completed").length;
  const ongoingCount = filteredEngagements.filter((e) => e.status === "Ongoing").length;

  // Quarter chart
  const quarterCounts: Record<string, number> = {};
  filteredEngagements.forEach((e) => {
    if (e.quarter) {
      e.quarter.split(",").map((q) => q.trim()).forEach((q) => {
        quarterCounts[q] = (quarterCounts[q] || 0) + 1;
      });
    }
  });
  const sortedQuarters = Object.entries(quarterCounts).sort(([a], [b]) => a.localeCompare(b));
  const maxQuarterCount = Math.max(...Object.values(quarterCounts), 1);

  // Handlers
  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : sortDir === "desc" ? null : "asc");
      if (sortDir === "desc") setSortKey(null);
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  const handleView = (eng: Engagement) => setViewingEng(eng);

  const handleEdit = (eng: Engagement) => {
    setEditingId(eng.id);
    setForm({
      customer: eng.customer || "",
      engagement_title: eng.engagement_title,
      engagement_type: eng.engagement_type,
      status: eng.status,
      actionable_outcome: eng.actionable_outcome,
      ae: eng.ae,
      asq_url: eng.asq_url,
      asq_id: eng.asq_id,
      timeframe: eng.timeframe,
      fy: eng.fy,
      quarter: eng.quarter,
      related_documents: eng.related_documents,
      next_steps: eng.next_steps,
      uco_ids: eng.uco_ids,
    });
    setShowForm(true);
  };

  const handleNew = () => {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setShowForm(true);
  };

  const handleSave = async () => {
    if (!form.customer?.trim()) return;
    setSubmitting(true);
    try {
      if (editingId) {
        await updateEngagement(editingId, form);
      } else {
        await createEngagement(form as Omit<Engagement, "id">);
      }
      setShowForm(false);
      setEditingId(null);
      setForm(EMPTY_FORM);
      await loadEngagements();
    } catch (e) {
      console.error("Failed to save engagement:", e);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteEngagement(id);
      setEngagements((prev) => prev.filter((e) => e.id !== id));
      setDeleteConfirm(null);
    } catch (e) {
      console.error("Failed to delete engagement:", e);
    }
  };

  const updateField = (field: string, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value || null }));
  };

  const updateColFilter = (col: keyof ColumnFilter, val: string) => {
    setColFilters((prev) => ({ ...prev, [col]: val }));
  };

  const hasAnyFilter = searchQuery || fyFilter || typeFilter || statusFilter || Object.values(colFilters).some(Boolean);

  const clearAll = () => {
    setSearchQuery("");
    setFyFilter("");
    setTypeFilter("");
    setStatusFilter("");
    setColFilters(EMPTY_COL_FILTERS);
    setSortKey(null);
    setSortDir(null);
  };

  function SortIcon({ col }: { col: SortKey }) {
    if (sortKey !== col) return <ArrowUpDown className="h-3 w-3 text-muted-foreground/50" />;
    if (sortDir === "asc") return <ArrowUp className="h-3 w-3 text-primary" />;
    return <ArrowDown className="h-3 w-3 text-primary" />;
  }

  // Unique values for column filter dropdowns
  const uniqueVals = useMemo(() => ({
    engagement_type: [...new Set(engagements.map((e) => e.engagement_type).filter(Boolean))] as string[],
    status: [...new Set(engagements.map((e) => e.status).filter(Boolean))] as string[],
    fy: [...new Set(engagements.map((e) => e.fy).filter(Boolean))] as string[],
    ae: [...new Set(engagements.map((e) => e.ae).filter(Boolean))] as string[],
  }), [engagements]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Engagements</h1>
          <p className="text-muted-foreground mt-1">
            Track, manage, and analyze engagement records across fiscal years, types, and accounts.
          </p>
        </div>
        <Button onClick={handleNew} className="gap-2">
          <Plus className="h-4 w-4" /> New Engagement
        </Button>
      </div>

      {/* Filters Bar */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium">Filters:</span>
            </div>

            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                placeholder="Search all fields..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8 w-56 h-8 text-sm"
              />
            </div>

            <select
              value={fyFilter}
              onChange={(e) => setFyFilter(e.target.value)}
              className="rounded-md border bg-background px-3 py-1.5 text-sm"
            >
              <option value="">All FY</option>
              {FY_OPTIONS.map((fy) => (
                <option key={fy} value={fy}>{fy}</option>
              ))}
            </select>

            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="rounded-md border bg-background px-3 py-1.5 text-sm"
            >
              <option value="">All Types</option>
              {ENGAGEMENT_TYPES.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>

            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-md border bg-background px-3 py-1.5 text-sm"
            >
              <option value="">All Status</option>
              {STATUS_OPTIONS.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>

            {hasAnyFilter && (
              <Button variant="ghost" size="sm" onClick={clearAll}>
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
                  <span className="text-xs font-mono w-20 text-right text-muted-foreground">{quarter}</span>
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
            {hasAnyFilter && " (filtered)"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-muted-foreground text-sm">Loading...</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  {/* Sortable column headers */}
                  <tr className="border-b text-left">
                    {([
                      ["customer", "Customer"],
                      ["engagement_title", "Title"],
                      ["engagement_type", "Type"],
                      ["status", "Status"],
                      ["fy", "FY"],
                      ["quarter", "Quarter"],
                      ["ae", "AE"],
                      ["asq_id", "ASQ"],
                    ] as [SortKey, string][]).map(([key, label]) => (
                      <th key={key} className="pb-1 font-medium">
                        <button
                          onClick={() => handleSort(key)}
                          className="flex items-center gap-1 hover:text-primary transition-colors"
                        >
                          {label}
                          <SortIcon col={key} />
                        </button>
                      </th>
                    ))}
                    <th className="pb-1 font-medium w-28">Action</th>
                  </tr>
                  {/* Per-column filter row */}
                  <tr className="border-b">
                    <td className="py-1 pr-1">
                      <Input
                        value={colFilters.customer}
                        onChange={(e) => updateColFilter("customer", e.target.value)}
                        placeholder="Filter..."
                        className="h-6 text-xs px-1.5"
                      />
                    </td>
                    <td className="py-1 pr-1">
                      <Input
                        value={colFilters.engagement_title}
                        onChange={(e) => updateColFilter("engagement_title", e.target.value)}
                        placeholder="Filter..."
                        className="h-6 text-xs px-1.5"
                      />
                    </td>
                    <td className="py-1 pr-1">
                      <select
                        value={colFilters.engagement_type}
                        onChange={(e) => updateColFilter("engagement_type", e.target.value)}
                        className="h-6 w-full rounded border bg-background text-xs px-1"
                      >
                        <option value="">All</option>
                        {uniqueVals.engagement_type.map((v) => (
                          <option key={v} value={v}>{v}</option>
                        ))}
                      </select>
                    </td>
                    <td className="py-1 pr-1">
                      <select
                        value={colFilters.status}
                        onChange={(e) => updateColFilter("status", e.target.value)}
                        className="h-6 w-full rounded border bg-background text-xs px-1"
                      >
                        <option value="">All</option>
                        {uniqueVals.status.map((v) => (
                          <option key={v} value={v}>{v}</option>
                        ))}
                      </select>
                    </td>
                    <td className="py-1 pr-1">
                      <select
                        value={colFilters.fy}
                        onChange={(e) => updateColFilter("fy", e.target.value)}
                        className="h-6 w-full rounded border bg-background text-xs px-1"
                      >
                        <option value="">All</option>
                        {uniqueVals.fy.map((v) => (
                          <option key={v} value={v}>{v}</option>
                        ))}
                      </select>
                    </td>
                    <td className="py-1 pr-1">
                      <Input
                        value={colFilters.quarter}
                        onChange={(e) => updateColFilter("quarter", e.target.value)}
                        placeholder="Filter..."
                        className="h-6 text-xs px-1.5"
                      />
                    </td>
                    <td className="py-1 pr-1">
                      <select
                        value={colFilters.ae}
                        onChange={(e) => updateColFilter("ae", e.target.value)}
                        className="h-6 w-full rounded border bg-background text-xs px-1"
                      >
                        <option value="">All</option>
                        {uniqueVals.ae.map((v) => (
                          <option key={v} value={v}>{v}</option>
                        ))}
                      </select>
                    </td>
                    <td className="py-1 pr-1">
                      <Input
                        value={colFilters.asq_id}
                        onChange={(e) => updateColFilter("asq_id", e.target.value)}
                        placeholder="Filter..."
                        className="h-6 text-xs px-1.5"
                      />
                    </td>
                    <td></td>
                  </tr>
                </thead>
                <tbody>
                  {filteredEngagements.map((eng) => (
                    <tr key={eng.id} className="border-b last:border-0 hover:bg-muted/50 group">
                      <td className="py-2 font-medium">{eng.customer || "--"}</td>
                      <td className="py-2 text-muted-foreground max-w-[200px] truncate">
                        {eng.engagement_title || "--"}
                      </td>
                      <td className="py-2">{typeBadge(eng.engagement_type)}</td>
                      <td className="py-2">{statusBadge(eng.status)}</td>
                      <td className="py-2 text-muted-foreground">{eng.fy || "--"}</td>
                      <td className="py-2 text-muted-foreground">{eng.quarter || "--"}</td>
                      <td className="py-2 text-muted-foreground">{eng.ae || "--"}</td>
                      <td className="py-2">
                        {eng.asq_url ? (
                          <a
                            href={eng.asq_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-primary hover:underline inline-flex items-center gap-1 text-xs"
                          >
                            {eng.asq_id || "View"} <ExternalLink className="h-3 w-3" />
                          </a>
                        ) : (
                          <span className="text-muted-foreground text-xs">{eng.asq_id || "--"}</span>
                        )}
                      </td>
                      <td className="py-2">
                        <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => handleView(eng)} title="View">
                            <Eye className="h-3.5 w-3.5" />
                          </Button>
                          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => handleEdit(eng)} title="Edit">
                            <Pencil className="h-3.5 w-3.5" />
                          </Button>
                          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setDeleteConfirm(eng.id)} title="Delete">
                            <Trash2 className="h-3.5 w-3.5 text-destructive" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {filteredEngagements.length === 0 && (
                <p className="text-sm text-muted-foreground text-center py-8">
                  {hasAnyFilter ? "No engagements match your filters." : "No engagements yet. Add one to get started."}
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* View Dialog (read-only) */}
      <Dialog open={!!viewingEng} onOpenChange={(open) => { if (!open) setViewingEng(null); }}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{viewingEng?.customer || "Engagement"}</DialogTitle>
            <DialogDescription>{viewingEng?.engagement_title || "Engagement details"}</DialogDescription>
          </DialogHeader>
          {viewingEng && (
            <div className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
              <div><span className="text-muted-foreground">Customer</span><p className="font-medium">{viewingEng.customer || "--"}</p></div>
              <div><span className="text-muted-foreground">Engagement Title</span><p className="font-medium">{viewingEng.engagement_title || "--"}</p></div>
              <div><span className="text-muted-foreground">Type</span><div className="mt-0.5">{typeBadge(viewingEng.engagement_type)}</div></div>
              <div><span className="text-muted-foreground">Status</span><div className="mt-0.5">{statusBadge(viewingEng.status)}</div></div>
              <div><span className="text-muted-foreground">Fiscal Year</span><p className="font-medium">{viewingEng.fy || "--"}</p></div>
              <div><span className="text-muted-foreground">Quarter</span><p className="font-medium">{viewingEng.quarter || "--"}</p></div>
              <div><span className="text-muted-foreground">Account Executive</span><p className="font-medium">{viewingEng.ae || "--"}</p></div>
              <div><span className="text-muted-foreground">Timeframe</span><p className="font-medium">{viewingEng.timeframe || "--"}</p></div>
              <div><span className="text-muted-foreground">ASQ ID</span><p className="font-medium">{viewingEng.asq_id || "--"}</p></div>
              <div>
                <span className="text-muted-foreground">ASQ URL</span>
                {viewingEng.asq_url ? (
                  <a href={viewingEng.asq_url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-primary hover:underline font-medium">
                    Open <ExternalLink className="h-3 w-3" />
                  </a>
                ) : (
                  <p className="font-medium">--</p>
                )}
              </div>
              <div className="col-span-2"><span className="text-muted-foreground">UCO IDs</span><p className="font-medium">{viewingEng.uco_ids || "--"}</p></div>
              <div className="col-span-2"><span className="text-muted-foreground">Actionable Outcome</span><p className="font-medium whitespace-pre-wrap">{viewingEng.actionable_outcome || "--"}</p></div>
              <div className="col-span-2"><span className="text-muted-foreground">Next Steps</span><p className="font-medium whitespace-pre-wrap">{viewingEng.next_steps || "--"}</p></div>
              <div className="col-span-2"><span className="text-muted-foreground">Related Documents</span><p className="font-medium whitespace-pre-wrap">{viewingEng.related_documents || "--"}</p></div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setViewingEng(null)}>Close</Button>
            <Button onClick={() => { if (viewingEng) { handleEdit(viewingEng); setViewingEng(null); } }}>
              <Pencil className="h-4 w-4 mr-2" /> Edit
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Add/Edit Dialog */}
      <Dialog open={showForm} onOpenChange={(open) => { if (!open) { setShowForm(false); setEditingId(null); } }}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editingId ? "Edit Engagement" : "New Engagement"}</DialogTitle>
            <DialogDescription>
              {editingId ? "Update the engagement details below." : "Fill in the details for a new engagement."}
            </DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="customer">Customer *</Label>
              <Input id="customer" value={form.customer || ""} onChange={(e) => updateField("customer", e.target.value)} placeholder="e.g. Deutsche Boerse" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="engagement_title">Engagement Title</Label>
              <Input id="engagement_title" value={form.engagement_title || ""} onChange={(e) => updateField("engagement_title", e.target.value)} placeholder="e.g. AI-centered stock exchange" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="engagement_type">Engagement Type</Label>
              <select id="engagement_type" value={form.engagement_type || ""} onChange={(e) => updateField("engagement_type", e.target.value)} className="w-full rounded-md border bg-background px-3 py-2 text-sm">
                <option value="">Select...</option>
                {ENGAGEMENT_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="status">Status</Label>
              <select id="status" value={form.status || ""} onChange={(e) => updateField("status", e.target.value)} className="w-full rounded-md border bg-background px-3 py-2 text-sm">
                <option value="">Select...</option>
                {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="fy">Fiscal Year</Label>
              <select id="fy" value={form.fy || ""} onChange={(e) => updateField("fy", e.target.value)} className="w-full rounded-md border bg-background px-3 py-2 text-sm">
                <option value="">Select...</option>
                {FY_OPTIONS.map((f) => <option key={f} value={f}>{f}</option>)}
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="quarter">Quarter</Label>
              <Input id="quarter" value={form.quarter || ""} onChange={(e) => updateField("quarter", e.target.value)} placeholder="e.g. FY26Q1, FY26Q2" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="ae">Account Executive</Label>
              <Input id="ae" value={form.ae || ""} onChange={(e) => updateField("ae", e.target.value)} placeholder="e.g. John Smith" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="timeframe">Timeframe</Label>
              <Input id="timeframe" value={form.timeframe || ""} onChange={(e) => updateField("timeframe", e.target.value)} placeholder="e.g. Q1-Q2 FY26" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="asq_id">ASQ ID</Label>
              <Input id="asq_id" value={form.asq_id || ""} onChange={(e) => updateField("asq_id", e.target.value)} placeholder="e.g. ASQ-12345" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="asq_url">ASQ URL</Label>
              <Input id="asq_url" value={form.asq_url || ""} onChange={(e) => updateField("asq_url", e.target.value)} placeholder="https://..." />
            </div>
            <div className="col-span-2 space-y-2">
              <Label htmlFor="uco_ids">UCO IDs</Label>
              <Input id="uco_ids" value={form.uco_ids || ""} onChange={(e) => updateField("uco_ids", e.target.value)} placeholder="e.g. UCO-1234, UCO-5678" />
            </div>
            <div className="col-span-2 space-y-2">
              <Label htmlFor="actionable_outcome">Actionable Outcome</Label>
              <Textarea id="actionable_outcome" value={form.actionable_outcome || ""} onChange={(e) => updateField("actionable_outcome", e.target.value)} placeholder="Key outcomes and deliverables..." rows={2} />
            </div>
            <div className="col-span-2 space-y-2">
              <Label htmlFor="next_steps">Next Steps</Label>
              <Textarea id="next_steps" value={form.next_steps || ""} onChange={(e) => updateField("next_steps", e.target.value)} placeholder="Follow-up actions..." rows={2} />
            </div>
            <div className="col-span-2 space-y-2">
              <Label htmlFor="related_documents">Related Documents</Label>
              <Textarea id="related_documents" value={form.related_documents || ""} onChange={(e) => updateField("related_documents", e.target.value)} placeholder="Links to related docs, slides, etc." rows={2} />
            </div>
          </div>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => { setShowForm(false); setEditingId(null); }}>
              <X className="h-4 w-4 mr-2" /> Cancel
            </Button>
            <Button onClick={handleSave} disabled={!form.customer?.trim() || submitting}>
              <Save className="h-4 w-4 mr-2" /> {submitting ? "Saving..." : editingId ? "Update" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <Dialog open={deleteConfirm !== null} onOpenChange={(open) => { if (!open) setDeleteConfirm(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Engagement</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this engagement? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteConfirm(null)}>Cancel</Button>
            <Button variant="destructive" onClick={() => deleteConfirm && handleDelete(deleteConfirm)}>Delete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
