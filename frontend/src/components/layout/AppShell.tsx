import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { ApiBanner } from "./ApiBanner";

export function AppShell() {
  return (
    <div className="app-shell-bg min-h-screen flex dark font-sans text-slate-200 bg-[#080A11]">
      <Sidebar />
      <div className="flex-1 flex flex-col min-h-screen overflow-hidden">
        <ApiBanner />
        <main className="flex-1 overflow-auto p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
