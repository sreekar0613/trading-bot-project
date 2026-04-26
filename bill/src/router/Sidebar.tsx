import { useState } from "react";
import { Link } from "@tanstack/react-router";
import {
  BarChart3,
  Briefcase,
  CandlestickChart,
  ChevronLeft,
  ChevronRight,
  Globe,
  LayoutDashboard,
  ScrollText,
  Terminal,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
}

const NAV: NavItem[] = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/positions", label: "Positions", icon: Briefcase },
  { to: "/charting", label: "Charting", icon: CandlestickChart },
  { to: "/universe", label: "Universe", icon: Globe },
  { to: "/metrics", label: "Metrics", icon: BarChart3 },
  { to: "/trades", label: "Trades", icon: ScrollText },
  { to: "/logs", label: "Logs", icon: Terminal },
];

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const width = collapsed ? 64 : 220;

  return (
    <aside
      className="fixed left-0 top-14 bottom-0 z-30 flex flex-col border-r border-border bg-surface transition-[width] duration-200"
      style={{ width }}
    >
      <nav className="flex flex-1 flex-col gap-1 p-2">
        {NAV.map(({ to, label, icon: Icon }) => (
          <Link
            key={to}
            to={to}
            className="flex items-center gap-3 rounded-input px-3 py-2 text-sm text-text-secondary hover:bg-bg hover:text-text-primary [&.active]:bg-bg [&.active]:text-text-primary"
            activeProps={{ className: "active" }}
          >
            <Icon size={18} className="shrink-0" />
            {!collapsed && <span>{label}</span>}
          </Link>
        ))}
      </nav>
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        className="m-2 flex h-8 items-center justify-center rounded-input border border-border text-text-secondary hover:bg-bg"
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
      </button>
    </aside>
  );
}
