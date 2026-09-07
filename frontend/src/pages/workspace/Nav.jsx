import { cn } from "@/lib/utils";
import { TONE } from "@/components/StatusChip";

export function NavItem({ icon: Icon, label, section, active, onClick, badge, tone, badgeTitle }) {
  const isActive = active === section;
  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full flex items-center gap-2.5 h-8 px-2.5 rounded-sm text-[13px] transition-colors group",
        isActive ? "bg-secondary text-foreground font-medium" : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
      )}
      data-testid={`nav-${section}`}
    >
      {isActive && <span className="absolute left-0 w-[3px] h-4 rounded-full" style={{ background: "var(--c-action)" }} />}
      <Icon className="h-4 w-4 shrink-0" strokeWidth={1.5} />
      <span className="truncate" title={label}>{label}</span>
      {badge != null && (
        <span className="ml-auto text-[10px] font-mono px-1.5 py-0.5 rounded-sm" title={badgeTitle} style={{ background: TONE[tone || "warning"].bg, color: TONE[tone || "warning"].fg }}>{badge}</span>
      )}
    </button>
  );
}

export const NavGroup = ({ title, children }) => (
  <div className="mb-4">
    <div className="px-2.5 mb-1.5 text-[10px] uppercase tracking-[0.14em] text-muted-foreground/70">{title}</div>
    <div className="space-y-0.5 relative">{children}</div>
  </div>
);
