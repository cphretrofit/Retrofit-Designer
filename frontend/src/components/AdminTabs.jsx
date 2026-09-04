import { NavLink } from "react-router-dom";

const TABS = [
  { to: "/users", label: "Users" },
  { to: "/maintenance", label: "Maintenance" },
];

export function AdminTabs() {
  return (
    <div className="flex items-center gap-1 border-b border-border mb-8" data-testid="admin-tabs">
      {TABS.map((t) => (
        <NavLink
          key={t.to}
          to={t.to}
          data-testid={`admin-tab-${t.label.toLowerCase()}`}
          className={({ isActive }) =>
            `px-4 h-9 flex items-center text-[13px] border-b-2 -mb-px transition-colors ${
              isActive ? "border-foreground text-foreground font-medium" : "border-transparent text-muted-foreground hover:text-foreground"
            }`
          }
        >
          {t.label}
        </NavLink>
      ))}
    </div>
  );
}
