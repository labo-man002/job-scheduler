import { NavLink, Outlet } from "react-router-dom";
import { TriangleAlert } from "lucide-react";

function subNavClass({ isActive }: { isActive: boolean }) {
  return `px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
    isActive ? "bg-secondary" : "text-muted-foreground hover:bg-secondary/50 hover:text-foreground"
  }`;
}

export function AdminLayout() {
  return (
    <div className="p-6 space-y-4">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">Admin</h1>
        <div className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          <TriangleAlert className="size-4 shrink-0" />
          No authentication yet (#60) -- these views are wide open to anyone who can reach this app.
        </div>
      </div>
      <div className="flex gap-1 border-b pb-2">
        <NavLink to="/admin/institutes" className={subNavClass}>
          Institutes
        </NavLink>
        <NavLink to="/admin/clients" className={subNavClass}>
          Clients
        </NavLink>
        <NavLink to="/admin/quotas" className={subNavClass}>
          Quotas
        </NavLink>
        <NavLink to="/admin/reservations" className={subNavClass}>
          Reservations
        </NavLink>
      </div>
      <Outlet />
    </div>
  );
}
