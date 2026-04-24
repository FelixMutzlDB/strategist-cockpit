interface CanvasBoxProps {
  id: string;
  label: string;
  onClick: (id: string, label: string) => void;
  className?: string;
}

function CanvasBox({ id, label, onClick, className = "" }: CanvasBoxProps) {
  return (
    <button
      onClick={() => onClick(id, label)}
      className={`rounded-lg border bg-background px-3 py-2 text-xs font-medium text-foreground shadow-sm hover:bg-accent hover:border-primary/30 transition-all cursor-pointer text-center ${className}`}
    >
      {label}
    </button>
  );
}

function SectionLabel({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`text-xs font-semibold text-muted-foreground uppercase tracking-wider ${className}`}>
      {children}
    </div>
  );
}

interface StrategistCanvasProps {
  onBoxClick: (activityId: string, label: string) => void;
}

export function StrategistCanvas({ onBoxClick }: StrategistCanvasProps) {
  return (
    <div className="rounded-xl border bg-card p-6 space-y-4 overflow-x-auto">
      {/* Goal column + Main content */}
      <div className="flex gap-4">
        {/* Left: Goal + Archetypes */}
        <div className="shrink-0 w-44 space-y-2">
          <div className="rounded-lg border-2 border-slate-200 bg-slate-50 p-3 space-y-1.5">
            <div className="text-xs font-bold text-slate-700 uppercase">Goal</div>
            <div className="text-xs text-slate-900 font-medium leading-snug">
              Databricks as the DEFAULT Data & AI Platform
            </div>
            <div className="space-y-0.5 text-[10px] text-slate-600">
              <div className="font-semibold">#1 AI/BI Genie</div>
              <div className="font-semibold">#2 Lakebase</div>
              <div>Unity Catalog</div>
              <div>Dominate DWH</div>
              <div>Lakeflow ETL</div>
              <div>Lead w/ Industry</div>
              <div>Win Enterprise AI</div>
            </div>
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50/50 p-3 space-y-2">
            <div className="text-xs font-bold text-slate-700 uppercase">Archetypes</div>
            <div className="text-[10px] text-muted-foreground leading-snug mb-1">
              Role designations guiding time outside direct account work
            </div>
            <div className="space-y-1.5">
              <a href="https://docs.google.com/presentation/d/1o8s_JZuIMqAQ_iHAkinINxntrvGJJbprFKmP3Nf6bOk/edit#slide=id.g3421452484c_0_5" target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 rounded-md border bg-teal-800 px-2 py-1.5 hover:opacity-90 transition-opacity cursor-pointer">
                <svg className="h-4 w-4 shrink-0 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
                <span className="text-[10px] font-medium text-white leading-tight">Organizer</span>
              </a>
              <a href="https://docs.google.com/presentation/d/1o8s_JZuIMqAQ_iHAkinINxntrvGJJbprFKmP3Nf6bOk/edit#slide=id.g3421452484c_0_10" target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 rounded-md border bg-rose-900 px-2 py-1.5 hover:opacity-90 transition-opacity cursor-pointer">
                <svg className="h-4 w-4 shrink-0 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
                <span className="text-[10px] font-medium text-white leading-tight">Builder</span>
              </a>
              <a href="https://docs.google.com/presentation/d/1o8s_JZuIMqAQ_iHAkinINxntrvGJJbprFKmP3Nf6bOk/edit#slide=id.g3421452484c_0_15" target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 rounded-md border bg-red-500 px-2 py-1.5 hover:opacity-90 transition-opacity cursor-pointer">
                <svg className="h-4 w-4 shrink-0 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
                <span className="text-[10px] font-medium text-white leading-tight">Product</span>
              </a>
              <a href="https://docs.google.com/presentation/d/1o8s_JZuIMqAQ_iHAkinINxntrvGJJbprFKmP3Nf6bOk/edit#slide=id.g3421452484c_0_20" target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 rounded-md border bg-emerald-600 px-2 py-1.5 hover:opacity-90 transition-opacity cursor-pointer">
                <svg className="h-4 w-4 shrink-0 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/></svg>
                <span className="text-[10px] font-medium text-white leading-tight">Industry</span>
              </a>
              <a href="https://docs.google.com/presentation/d/1o8s_JZuIMqAQ_iHAkinINxntrvGJJbprFKmP3Nf6bOk/edit#slide=id.g3421452484c_0_25" target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 rounded-md border bg-teal-600 px-2 py-1.5 hover:opacity-90 transition-opacity cursor-pointer">
                <svg className="h-4 w-4 shrink-0 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
                <span className="text-[10px] font-medium text-white leading-tight">Advisor</span>
              </a>
            </div>
          </div>
        </div>

        {/* Center: Main Framework */}
        <div className="flex-1 space-y-3 min-w-[600px]">
          {/* Thought Leadership */}
          <div className="rounded-lg border bg-muted/30 p-4 space-y-3">
            <SectionLabel>Thought Leadership</SectionLabel>
            <p className="text-[10px] text-muted-foreground -mt-2">
              Translate business vision into data & AI program and org change in becoming data forward
            </p>

            {/* Customer Engagements [50%] + Evangelism [10%] */}
            <div className="flex gap-3">
              {/* Customer Engagements */}
              <div className="flex-1 rounded-md border bg-background/50 p-3 space-y-2">
                <div className="text-xs font-semibold">Customer Engagements [50%]</div>
                <div className="grid grid-cols-3 gap-2">
                  <CanvasBox id="c-level-vision-setting" label="C-level vision setting" onClick={onBoxClick} />
                  <CanvasBox id="elevate-the-pitch" label="Elevate the pitch" onClick={onBoxClick} />
                  <CanvasBox id="events-customer" label="Events" onClick={onBoxClick} />
                  <CanvasBox id="data-ai-strategy" label="Data & AI Strategy (design/review)" onClick={onBoxClick} />
                  <CanvasBox id="targeted-customer-engagements" label="Targeted customer engagements" onClick={onBoxClick} />
                  <CanvasBox id="market-scouting-customer" label="Market Scouting" onClick={onBoxClick} />
                  <CanvasBox id="strategic-hunting" label="Strategic Hunting" onClick={onBoxClick} />
                  <CanvasBox id="measuring-success" label="Measuring Success" onClick={onBoxClick} />
                </div>
              </div>

              {/* Evangelism */}
              <div className="w-40 rounded-md border bg-background/50 p-3 space-y-2">
                <div className="text-xs font-semibold">Evangelism [10%]</div>
                <div className="space-y-2">
                  <CanvasBox id="events-evangelism" label="Events" onClick={onBoxClick} />
                  <CanvasBox id="market-scouting-evangelism" label="Market Scouting" onClick={onBoxClick} />
                  <CanvasBox id="community-seeding-evangelism" label="Community Seeding" onClick={onBoxClick} />
                </div>
              </div>
            </div>

            {/* Additional boxes */}
            <div className="grid grid-cols-3 gap-2">
              <CanvasBox id="champion-building" label="Champion Building" onClick={onBoxClick} />
              <CanvasBox id="customer-mobilization" label="Customer Mobilization" onClick={onBoxClick} />
              <CanvasBox id="community-seeding-thought-leadership" label="Community Seeding" onClick={onBoxClick} />
              <CanvasBox id="focused-account-planning" label="Focused account planning" onClick={onBoxClick} />
            </div>
          </div>

          {/* Coaching & Mentoring + Customer Mobilization row */}
          <div className="flex gap-3">
            <div className="flex-1 rounded-lg border bg-muted/30 p-4 space-y-2">
              <SectionLabel>Coaching & Mentoring</SectionLabel>
              <p className="text-[10px] text-muted-foreground">Individuals, teams, customers</p>
              <CanvasBox id="individual-coaching" label="Individual Coaching" onClick={onBoxClick} />
            </div>
            <div className="flex-1 rounded-lg border bg-muted/30 p-4 space-y-2">
              <SectionLabel>Customer Mobilization</SectionLabel>
              <p className="text-[10px] text-muted-foreground">Overcome inertia, accelerate consumption, grow the community</p>
              <CanvasBox id="adoption-frameworks" label="Adoption Frameworks" onClick={onBoxClick} />
            </div>
          </div>

          {/* Initiatives [20%] */}
          <div className="rounded-lg border bg-muted/30 p-4 space-y-2">
            <SectionLabel>Initiatives [20%]</SectionLabel>
            <div className="grid grid-cols-3 gap-2">
              <CanvasBox id="strategist-role" label="Strategist Role (incl. metrics)" onClick={onBoxClick} />
              <CanvasBox id="strategy-cop" label="Strategy CoP" onClick={onBoxClick} />
              <CanvasBox id="reusable-strategy-assets" label="Reusable Strategy Assets" onClick={onBoxClick} />
            </div>
          </div>

          {/* Admin & Research */}
          <div className="rounded-lg border bg-muted/30 p-4 space-y-2">
            <SectionLabel>Admin & Research</SectionLabel>
            <div className="grid grid-cols-3 gap-2">
              <CanvasBox id="strategy-research" label="Strategy research" onClick={onBoxClick} />
            </div>
          </div>

          <div className="text-[10px] text-muted-foreground italic">
            Development: role, organization, metrics
          </div>
        </div>

        {/* Right: Impact */}
        <div className="shrink-0 w-48 space-y-3">
          <div className="rounded-lg border bg-muted/30 p-3 space-y-2">
            <div className="text-xs font-bold uppercase text-muted-foreground">Impact</div>
            <div className="text-[10px] text-muted-foreground">Leading indicators & metrics</div>

            <div className="space-y-2 text-[10px]">
              <div>
                <div className="font-semibold text-xs mb-1">Customer Engagements</div>
                <ul className="space-y-0.5 text-muted-foreground list-disc list-inside">
                  <li>Jointly developed data & AI programs</li>
                  <li>Use case discovery / pipeline generation</li>
                  <li>Pipeline velocity (mobilization)</li>
                  <li># focused acct planning sessions</li>
                  <li># exec meetings</li>
                </ul>
              </div>

              <div>
                <div className="font-semibold text-xs mb-1">Evangelism</div>
                <ul className="space-y-0.5 text-muted-foreground list-disc list-inside">
                  <li># events, podcasts, publications</li>
                  <li>Social media reach</li>
                  <li># engaged decision makers</li>
                </ul>
              </div>

              <div>
                <div className="font-semibold text-xs mb-1">Initiatives</div>
                <ul className="space-y-0.5 text-muted-foreground list-disc list-inside">
                  <li># of reusable assets/programs</li>
                  <li># of mentees / coachings</li>
                  <li>Initiative impact (MAU, pipeline, ...)</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
