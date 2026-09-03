import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getDashboard, getProjects } from "@/lib/api";
import { TopBar, Meter } from "@/components/Shell";
import { StatusChip } from "@/components/StatusChip";
import { ArrowRight, AlertTriangle, Clock, ShieldCheck, Layers, Plus, FileStack, Search, Building2, ClipboardList } from "lucide-react";
import { cn } from "@/lib/utils";

const KPI = ({ label, value, unit, tone, icon: Icon, sub, testid }) => (
  <div className="relative p-5 border-r border-border last:border-r-0 group" data-testid={testid}>
    <div className="flex items-center justify-between">
      <span className="text-[11px] text-muted-foreground uppercase tracking-[0.12em]">{label}</span>
      <Icon className="h-4 w-4 text-muted-foreground/60" strokeWidth={1.5} />
    </div>
    <div className="mt-3 flex items-baseline gap-1.5">
      <span className="font-display font-300 text-[42px] leading-none tabular-nums" style={tone ? { color: tone } : {}} data-testid={`${testid}-value`}>{value}</span>
      {unit && <span className="text-sm text-muted-foreground font-mono">{unit}</span>}
    </div>
    {sub && <div className="mt-2 text-[11px] text-muted-foreground">{sub}</div>}
  </div>
);

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [allProjects, setAllProjects] = useState([]);
  const [q, setQ] = useState("");
  const [sf, setSf] = useState(null);
  const [pf, setPf] = useState(null);
  const navigate = useNavigate();

  useEffect(() => { getDashboard().then(setData).catch(() => {}); }, []);
  useEffect(() => { getProjects().then(setAllProjects).catch(() => {}); }, []);

  const stats = data?.stats;
  const projects = data?.projects || [];
  const ql = q.trim().toLowerCase();
  const partners = [...new Set(allProjects.map((p) => p.partner).filter(Boolean))].sort();
  const filtersOn = ql || sf || pf;
  const base = filtersOn ? allProjects : projects;
  const list = base.filter((p) => {
    const okQ = !ql || [p.name, p.ref, p.town, p.address, p.measureSummary, p.status]
      .filter(Boolean).some((s) => String(s).toLowerCase().includes(ql));
    const okS = !sf || p.status === sf;
    const okP = !pf || p.partner === pf;
    return okQ && okS && okP;
  });

  return (
    <div className="min-h-screen bg-background">
      <TopBar crumbs={[{ label: "Command Centre" }]} />
      <main className="max-w-[1360px] mx-auto px-5 py-8 anim-in">
        <div className="flex items-end justify-between mb-6">
          <div>
            <div className="text-[11px] text-muted-foreground uppercase tracking-[0.18em] mb-1">Portfolio</div>
            <h1 className="font-display font-300 text-3xl tracking-tight">Design Command Centre</h1>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => navigate("/clients")}
              className="flex items-center gap-2 h-9 px-4 border border-border rounded-sm text-[13px] font-medium hover:bg-secondary transition-colors"
              data-testid="clients-nav-button"
            >
              <Building2 className="h-4 w-4" strokeWidth={1.75} /> Clients
            </button>
            <button
              onClick={() => navigate("/templates")}
              className="flex items-center gap-2 h-9 px-4 border border-border rounded-sm text-[13px] font-medium hover:bg-secondary transition-colors"
              data-testid="templates-nav-button"
            >
              <FileStack className="h-4 w-4" strokeWidth={1.75} /> Templates
            </button>
            <button
              onClick={() => navigate("/import")}
              className="flex items-center gap-2 h-9 px-4 bg-primary text-primary-foreground rounded-sm text-[13px] font-medium hover:opacity-90 transition-opacity"
              data-testid="new-project-button"
            >
              <Plus className="h-4 w-4" strokeWidth={2} /> New Retrofit Design
            </button>
          </div>
        </div>

        {/* KPI band */}
        <div className="grid grid-cols-2 lg:grid-cols-4 border border-border rounded-sm bg-card overflow-hidden">
          <KPI label="Active Projects" value={stats?.activeProjects ?? "—"} icon={Layers} sub="Across 6 delivery partners" testid="kpi-active-projects" />
          <KPI label="Ready for QA" value={stats?.readyForQA ?? "—"} icon={ShieldCheck} tone="var(--c-info)" sub="Awaiting coordinator review" testid="kpi-ready-qa" />
          <KPI label="Require Attention" value={stats?.requireAttention ?? "—"} icon={AlertTriangle} tone="var(--c-critical)" sub="Blocking items open" testid="kpi-attention" />
          <KPI label="Avg Design Time" value={stats?.avgDesignTime ?? "—"} unit="min" icon={Clock} sub="↓ from 2–3 hrs baseline" testid="kpi-design-time" />
        </div>

        {/* Project table */}
        <div className="mt-8 border border-border rounded-sm bg-card">
          <div className="flex items-center justify-between px-5 h-12 border-b border-border gap-4">
            <span className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground whitespace-nowrap">{ql ? "Search Results" : "Recent Projects"}</span>
            <div className="relative flex-1 max-w-sm ml-auto">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" strokeWidth={1.75} />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search properties by name, ref, town or measure…"
                data-testid="property-search-input"
                className="w-full h-8 pl-9 pr-3 bg-background border border-border rounded-sm text-[12.5px] outline-none focus:border-foreground/30 transition-colors"
              />
            </div>
            <span className="text-[11px] font-mono text-muted-foreground whitespace-nowrap" data-testid="project-count">{list.length} {ql ? "found" : "shown"}</span>
          </div>
          <div className="flex items-center gap-2 px-5 py-2.5 border-b border-border flex-wrap" data-testid="dashboard-filters">
            {[["require_attention", "Requires Attention"], ["ready_for_qa", "Ready for QA"], ["in_progress", "In Progress"], ["approved", "Approved"]].map(([v, l]) => (
              <button key={v} onClick={() => setSf(sf === v ? null : v)} data-testid={`filter-status-${v}`}
                className={cn("text-[11px] px-2.5 h-7 rounded-sm border transition-colors", sf === v ? "bg-primary text-primary-foreground border-primary" : "border-border text-muted-foreground hover:bg-secondary")}>{l}</button>
            ))}
            <select value={pf || ""} onChange={(e) => setPf(e.target.value || null)} data-testid="filter-partner"
              className="ml-auto h-7 px-2 bg-background border border-border rounded-sm text-[11.5px] text-muted-foreground outline-none">
              <option value="">All partners</option>
              {partners.map((pn) => <option key={pn} value={pn}>{pn}</option>)}
            </select>
            {(sf || pf) && <button onClick={() => { setSf(null); setPf(null); }} data-testid="filter-clear" className="text-[11px] text-muted-foreground hover:text-foreground">Clear</button>}
          </div>
          <div className="grid grid-cols-[1.6fr_1fr_1.1fr_0.9fr_auto] px-5 h-9 items-center text-[10.5px] uppercase tracking-[0.1em] text-muted-foreground border-b border-border">
            <span>Property</span>
            <span className="hidden md:block">Measures</span>
            <span>Completion</span>
            <span>Status</span>
            <span></span>
          </div>
          {list.map((p, i) => (
            <button
              key={p.id}
              onClick={() => navigate(`/project/${p.id}`)}
              className="w-full grid grid-cols-[1.6fr_1fr_1.1fr_0.9fr_auto] px-5 py-3.5 items-center border-b border-border/70 last:border-b-0 hover:bg-secondary/60 transition-colors text-left group"
              data-testid={`project-row-${p.id}`}
              style={{ animationDelay: `${i * 30}ms` }}
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium truncate">{p.name}</span>
                  {p.actionsRequired > 0 && (
                    <span className="flex items-center gap-1 text-[10.5px] font-mono" style={{ color: "var(--c-warning)" }}>
                      <AlertTriangle className="h-3 w-3" strokeWidth={1.5} />{p.actionsRequired}
                    </span>
                  )}
                  {p.loftChecklistGap && (
                    <span data-testid={`loft-gap-${p.id}`} title="Loft & fabric checklist has unanswered (Unknown) items — resolve before issuing the pack"
                      className="flex items-center gap-1 text-[10.5px] font-mono" style={{ color: "var(--c-info)" }}>
                      <ClipboardList className="h-3 w-3" strokeWidth={1.5} />Loft
                    </span>
                  )}
                </div>
                <div className="text-[11.5px] text-muted-foreground font-mono mt-0.5">{p.ref} · {p.town}{p.partner ? ` · ${p.partner}` : ""}</div>
              </div>
              <div className="hidden md:block text-[12px] text-muted-foreground truncate pr-4">{p.measureSummary}</div>
              <div className="pr-6">
                <div className="flex items-center gap-2">
                  <Meter value={p.completion} className="max-w-[110px]" />
                  <span className="text-[12px] font-mono tabular-nums text-muted-foreground w-8">{p.completion}%</span>
                </div>
              </div>
              <div><StatusChip status={p.status} /></div>
              <div className="flex items-center gap-1.5 text-[12px] text-muted-foreground group-hover:text-foreground transition-colors font-medium">
                <span className="hidden lg:inline">Continue</span>
                <ArrowRight className="h-4 w-4 group-hover:translate-x-0.5 transition-transform" strokeWidth={1.5} />
              </div>
            </button>
          ))}
          {list.length === 0 && (
            <div className="px-5 py-12 text-center text-[13px] text-muted-foreground" data-testid="search-empty">
              No properties match “{q}”.
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
