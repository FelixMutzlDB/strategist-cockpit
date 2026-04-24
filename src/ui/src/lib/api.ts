const API_BASE = "/api";

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  if (res.status === 204) return {} as T;
  return res.json();
}

// --- Engagements ---
export interface Engagement {
  id: number;
  engagement_type: string | null;
  status: string | null;
  customer: string | null;
  engagement_title: string | null;
  actionable_outcome: string | null;
  ae: string | null;
  asq_url: string | null;
  asq_id: string | null;
  timeframe: string | null;
  fy: string | null;
  quarter: string | null;
  related_documents: string | null;
  next_steps: string | null;
  // Comma-separated Salesforce Use Case Object IDs, e.g. "UCO-1234, UCO-5678".
  uco_ids: string | null;
}

export function listEngagements(params?: {
  fy?: string;
  engagement_type?: string;
  status?: string;
  customer?: string;
}): Promise<Engagement[]> {
  const search = new URLSearchParams();
  if (params?.fy) search.set("fy", params.fy);
  if (params?.engagement_type) search.set("engagement_type", params.engagement_type);
  if (params?.status) search.set("status", params.status);
  if (params?.customer) search.set("customer", params.customer);
  const qs = search.toString();
  return fetchJSON(`/engagements/${qs ? `?${qs}` : ""}`);
}

export function createEngagement(engagement: Omit<Engagement, "id">): Promise<Engagement> {
  return fetchJSON("/engagements/", {
    method: "POST",
    body: JSON.stringify(engagement),
  });
}

export function updateEngagement(id: number, engagement: Partial<Engagement>): Promise<Engagement> {
  return fetchJSON(`/engagements/${id}`, {
    method: "PUT",
    body: JSON.stringify(engagement),
  });
}

export function deleteEngagement(id: number): Promise<void> {
  return fetchJSON(`/engagements/${id}`, { method: "DELETE" });
}

// --- Projects ---
export interface Project {
  id: number;
  name: string;
  description: string | null;
  url: string;
  thumbnail_url: string | null;
  category: string | null;
  created_at: string | null;
}

export function listProjects(): Promise<Project[]> {
  return fetchJSON("/projects/");
}

export function createProject(project: {
  name: string;
  url: string;
  description?: string;
  category?: string;
}): Promise<Project> {
  return fetchJSON("/projects/", {
    method: "POST",
    body: JSON.stringify(project),
  });
}

export function deleteProject(id: number): Promise<void> {
  return fetchJSON(`/projects/${id}`, { method: "DELETE" });
}

// --- Chat ---
export interface ChatResponse {
  response: string;
  source: string;
}

export function sendChatMessage(message: string): Promise<ChatResponse> {
  return fetchJSON("/chat/", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

// --- Canvas ---
export interface CanvasSummary {
  activity: string;
  engagement_count: number;
  accounts: string[];
  recent_engagements: Engagement[];
}

export function getCanvasSummary(activity: string): Promise<CanvasSummary> {
  return fetchJSON(`/canvas/summary/${activity}`);
}
