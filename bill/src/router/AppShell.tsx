import type { ReactNode } from "react";
import { TopNav } from "./TopNav";
import { Sidebar } from "./Sidebar";

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="min-h-screen bg-bg text-text-primary">
      <TopNav />
      <Sidebar />
      <main className="pl-[64px] pt-14 transition-[padding] md:pl-[220px]">
        <div className="p-6">{children}</div>
      </main>
    </div>
  );
}
