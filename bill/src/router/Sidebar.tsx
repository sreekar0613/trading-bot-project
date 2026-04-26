import { useState } from "react";
import { Link } from "@tanstack/react-router";
import {
  BarChart2,
  CandlestickChart,
  ChevronLeft,
  ChevronRight,
  Globe,
  LayoutDashboard,
  Receipt,
  Terminal,
  TrendingUp,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Tooltip } from "@/components/Tooltip";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
}

const NAV: NavItem[] = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/positions", label: "Positions", icon: TrendingUp },
  { to: "/charting", label: "Charting", icon: CandlestickChart },
  { to: "/universe", label: "Universe", icon: Globe },
  { to: "/metrics", label: "Metrics", icon: BarChart2 },
  { to: "/trades", label: "Trades", icon: Receipt },
  { to: "/logs", label: "Logs", icon: Terminal },
];

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const width = collapsed ? 64 : 220;

  return (
    <aside
      className="fixed bottom-0 left-0 top-14 z-30 flex flex-col border-r border-border bg-surface transition-[width] duration-200"
      style={{ width }}
    >
      <nav className="flex flex-1 flex-col gap-0.5 p-2">
        {NAV.map((item) => (
          <SidebarLink key={item.to} item={item} collapsed={collapsed} />
        ))}
      </nav>
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        className="m-2 flex h-8 items-center justify-center rounded-input border border-border text-text-secondary transition-colors hover:bg-bg hover:text-text-primary"
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
      </button>
    </aside>
  );
}

function SidebarLink({ item, collapsed }: { item: NavItem; collapsed: boolean }) {
  const { to, label, icon: Icon } = item;

  const link = (
    <Link
      to={to}
      className={`group relative flex items-center rounded-input py-2 text-sm text-text-secondary transition-colors hover:bg-bg hover:text-text-primary [&.active]:bg-bg [&.active]:font-medium [&.active]:text-text-primary ${
        collapsed ? "justify-center px-0" : "gap-3 px-3"
      }`}
      activeProps={{ className: "active" }}
    >
      <span
        className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-text-primary opacity-0 transition-opacity group-[.active]:opacity-100"
        aria-hidden
      />
      <Icon size={18} className="shrink-0" />
      {!collapsed && <span>{label}</span>}
    </Link>
  );

  if (collapsed) {
    return (
      <Tooltip content={label} side="right">
        {link}
      </Tooltip>
    );
  }
  return link;
}
