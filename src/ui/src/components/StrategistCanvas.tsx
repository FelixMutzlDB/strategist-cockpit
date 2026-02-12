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
        {/* Left: Goal */}
        <div className="shrink-0 w-36 space-y-2">
          <div className="rounded-lg border-2 border-red-200 bg-red-50 p-3 space-y-1.5">
            <div className="text-xs font-bold text-red-700 uppercase">Goal</div>
            <div className="text-xs text-red-900 font-medium leading-snug">
              Databricks as the DEFAULT Data & AI Platform
            </div>
            <div className="space-y-0.5 text-[10px] text-red-700">
              <div>#1 Unity Catalog</div>
              <div>#2 Dominate DWH</div>
              <div>#3 Lakeflow ETL</div>
              <div>#4 Lead w/ Industry</div>
              <div>#5 Win Enterprise AI</div>
            </div>
          </div>
          <div className="rounded-lg border border-teal-200 bg-teal-50 p-3 space-y-1">
            <div className="text-xs font-bold text-teal-700">Advisor</div>
            <div className="text-[10px] text-teal-900 leading-snug">
              Excellence in particularly challenging or complex customer engagements
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
                  <CanvasBox id="events" label="Events" onClick={onBoxClick} />
                  <CanvasBox id="data-ai-strategy" label="Data & AI Strategy (design/review)" onClick={onBoxClick} />
                  <CanvasBox id="targeted-customer-engagements" label="Targeted customer engagements" onClick={onBoxClick} />
                  <CanvasBox id="market-scouting" label="Market Scouting" onClick={onBoxClick} />
                  <CanvasBox id="strategic-hunting" label="Strategic Hunting" onClick={onBoxClick} />
                  <CanvasBox id="measuring-success" label="Measuring Success" onClick={onBoxClick} />
                </div>
              </div>

              {/* Evangelism */}
              <div className="w-40 rounded-md border bg-background/50 p-3 space-y-2">
                <div className="text-xs font-semibold">Evangelism [10%]</div>
                <div className="space-y-2">
                  <CanvasBox id="events" label="Events" onClick={onBoxClick} />
                  <CanvasBox id="market-scouting" label="Market Scouting" onClick={onBoxClick} />
                  <CanvasBox id="community-seeding" label="Community Seeding" onClick={onBoxClick} />
                </div>
              </div>
            </div>

            {/* Additional boxes */}
            <div className="grid grid-cols-3 gap-2">
              <CanvasBox id="champion-building" label="Champion Building" onClick={onBoxClick} />
              <CanvasBox id="customer-mobilization" label="Customer Mobilization" onClick={onBoxClick} />
              <CanvasBox id="community-seeding" label="Community Seeding" onClick={onBoxClick} />
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
