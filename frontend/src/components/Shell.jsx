import { useNavigate } from "react-router-dom";
import { useState } from "react";
import { useTheme } from "@/context/ThemeProvider";
import { useAuth } from "@/context/AuthContext";
import { Command, Moon, Sun, Search, ChevronRight, LogOut, Users, ChevronDown, KeyRound } from "lucide-react";
import { cn } from "@/lib/utils";

function UserMenu() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  if (!user) return null;
  const initials = (user.name || user.email || "?").split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase();
  return (
    <div className="relative">
      <button onClick={() => setOpen((o) => !o)} onBlur={() => setTimeout(() => setOpen(false), 150)}
        data-testid="user-menu-button"
        className="flex items-center gap-2 h-8 pl-1 pr-2 border border-border rounded-sm hover:border-foreground/30 transition-colors">
        <span className="h-6 w-6 rounded-[3px] bg-foreground text-background text-[10px] font-medium flex items-center justify-center">{initials}</span>
        <span className="hidden sm:block text-[12px] max-w-[120px] truncate">{user.name}</span>
        <ChevronDown className="h-3 w-3 text-muted-foreground" strokeWidth={1.75} />
      </button>
      {open && (
        <div className="absolute right-0 mt-1.5 w-56 bg-card border border-border rounded-md shadow-lg py-1 z-50" data-testid="user-menu">
          <div className="px-3 py-2 border-b border-border">
            <div className="text-[13px] font-medium truncate">{user.name}</div>
            <div className="text-[11px] text-muted-foreground font-mono truncate">{user.email}</div>
            <div className="text-[10px] uppercase tracking-[0.1em] text-muted-foreground mt-1">{user.role === "admin" ? "Administrator" : "User"}</div>
          </div>
          {user.role === "admin" && (
            <button onMouseDown={() => navigate("/users")} data-testid="nav-users"
              className="w-full flex items-center gap-2 px-3 py-2 text-[13px] hover:bg-secondary transition-colors">
              <Users className="h-3.5 w-3.5 text-muted-foreground" strokeWidth={1.75} /> User Management
            </button>
          )}
          <button onMouseDown={() => navigate("/account/password")} data-testid="nav-change-password"
            className="w-full flex items-center gap-2 px-3 py-2 text-[13px] hover:bg-secondary transition-colors">
            <KeyRound className="h-3.5 w-3.5 text-muted-foreground" strokeWidth={1.75} /> Change password
          </button>
          <button onMouseDown={logout} data-testid="logout-button"
            className="w-full flex items-center gap-2 px-3 py-2 text-[13px] hover:bg-secondary transition-colors text-red-600">
            <LogOut className="h-3.5 w-3.5" strokeWidth={1.75} /> Sign out
          </button>
        </div>
      )}
    </div>
  );
}


export function TopBar({ crumbs = [], right = null }) {
  const { theme, toggle } = useTheme();
  const navigate = useNavigate();

  return (
    <header className="h-14 shrink-0 border-b border-border bg-background/80 backdrop-blur-md sticky top-0 z-30 flex items-center px-5 gap-4">
      <button
        onClick={() => navigate("/")}
        className="flex items-center gap-2.5 group"
        data-testid="brand-home-button"
      >
        <div className="h-7 w-7 border border-foreground/80 flex items-center justify-center rounded-[3px]">
          <div className="h-3 w-3 border-[1.5px] border-foreground rotate-45 group-hover:rotate-[135deg] transition-transform duration-300" />
        </div>
        <div className="leading-none">
          <div className="font-display font-800 text-[13px] tracking-tight">ORTHOGRAPH</div>
          <div className="text-[9px] text-muted-foreground tracking-[0.24em] uppercase mt-0.5">Retrofit Design</div>
        </div>
      </button>

      <div className="h-5 w-px bg-border mx-1" />

      <nav className="flex items-center gap-1.5 text-[13px] min-w-0">
        {crumbs.map((c, i) => (
          <div key={i} className="flex items-center gap-1.5 min-w-0">
            {i > 0 && <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/50 shrink-0" strokeWidth={1.5} />}
            {c.to ? (
              <button
                onClick={() => navigate(c.to)}
                className="text-muted-foreground hover:text-foreground transition-colors truncate"
              >
                {c.label}
              </button>
            ) : (
              <span className="text-foreground font-medium truncate">{c.label}</span>
            )}
          </div>
        ))}
      </nav>

      <div className="ml-auto flex items-center gap-2">
        {right}
        <button
          onClick={() => window.dispatchEvent(new Event("open-command-palette"))}
          className="hidden sm:flex items-center gap-2 h-8 pl-2.5 pr-1.5 border border-border rounded-sm text-muted-foreground hover:border-foreground/30 hover:text-foreground transition-colors group"
          data-testid="open-command-palette"
        >
          <Search className="h-3.5 w-3.5" strokeWidth={1.5} />
          <span className="text-[12px]">Search</span>
          <kbd className="flex items-center gap-0.5 text-[10px] font-mono bg-secondary px-1.5 py-0.5 rounded-[3px] border border-border">
            <Command className="h-2.5 w-2.5" strokeWidth={2} />K
          </kbd>
        </button>
        <button
          onClick={toggle}
          className="h-8 w-8 flex items-center justify-center border border-border rounded-sm text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors"
          data-testid="theme-toggle"
          aria-label="Toggle theme"
        >
          {theme === "dark" ? <Sun className="h-4 w-4" strokeWidth={1.5} /> : <Moon className="h-4 w-4" strokeWidth={1.5} />}
        </button>
        <UserMenu />
        <div className="h-8 w-8 rounded-full bg-foreground text-background flex items-center justify-center text-[11px] font-mono font-medium select-none">
          AO
        </div>
      </div>
    </header>
  );
}

export function ReadinessRing({ value, size = 132, stroke = 6, label = "READINESS" }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const off = c - (value / 100) * c;
  const color = value >= 90 ? "var(--c-pass)" : value >= 60 ? "var(--c-action)" : "var(--c-warning)";
  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="hsl(var(--border))" strokeWidth={stroke} />
        <circle
          cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke}
          strokeDasharray={c} strokeDashoffset={off} strokeLinecap="round"
          style={{ transition: "stroke-dashoffset 0.9s cubic-bezier(0.16,1,0.3,1)" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-display font-300 tabular-nums" style={{ fontSize: size * 0.3 }}>{value}<span className="text-[0.5em] align-top text-muted-foreground">%</span></span>
        <span className="text-[9px] text-muted-foreground tracking-[0.18em] mt-0.5">{label}</span>
      </div>
    </div>
  );
}

export function Meter({ value, className }) {
  const color = value >= 90 ? "var(--c-pass)" : value >= 60 ? "var(--c-action)" : "var(--c-warning)";
  return (
    <div className={cn("h-1 w-full bg-border/80 rounded-full overflow-hidden", className)}>
      <div
        className="h-full rounded-full"
        style={{ width: `${value}%`, backgroundColor: color, transition: "width 0.7s cubic-bezier(0.16,1,0.3,1)" }}
      />
    </div>
  );
}
