import { Navigate, NavLink, Route, Routes } from "react-router-dom";
import { Network, Boxes, LayoutDashboard, ListTodo, Moon, ShieldUser, Sun } from "lucide-react";
import { Toaster } from "sonner";
import { DashboardPage } from "@/pages/DashboardPage";
import { ClustersPage } from "@/pages/ClustersPage";
import { ClusterDetailPage } from "@/pages/ClusterDetailPage";
import { JobsPage } from "@/pages/JobsPage";
import { JobSubmitPage } from "@/pages/JobSubmitPage";
import { JobDetailPage } from "@/pages/JobDetailPage";
import { AdminLayout } from "@/pages/admin/AdminLayout";
import { AdminInstitutesPage } from "@/pages/admin/AdminInstitutesPage";
import { AdminClientsPage } from "@/pages/admin/AdminClientsPage";
import { AdminQuotasPage } from "@/pages/admin/AdminQuotasPage";
import { AdminReservationsPage } from "@/pages/admin/AdminReservationsPage";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/lib/useTheme";

function Nav() {
  const { theme, toggleTheme } = useTheme();
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
      isActive ? "bg-secondary" : "text-muted-foreground hover:bg-secondary/50 hover:text-foreground"
    }`;

  return (
    <nav className="border-b bg-background/95 backdrop-blur flex items-center gap-1 px-4 py-2">
      <div className="flex items-center gap-1.5 pr-4 mr-2 border-r">
        <Network className="size-4 text-primary" />
        <span className="text-sm font-semibold tracking-tight">Job Scheduler</span>
      </div>
      <NavLink to="/" end className={linkClass}>
        <LayoutDashboard className="size-4" />
        Dashboard
      </NavLink>
      <NavLink to="/clusters" className={linkClass}>
        <Boxes className="size-4" />
        Clusters
      </NavLink>
      <NavLink to="/jobs" className={linkClass}>
        <ListTodo className="size-4" />
        Jobs
      </NavLink>
      <NavLink to="/admin" className={linkClass}>
        <ShieldUser className="size-4" />
        Admin
      </NavLink>
      <Button
        variant="ghost"
        size="icon-sm"
        className="ml-auto"
        aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        onClick={toggleTheme}
      >
        {theme === "dark" ? <Sun /> : <Moon />}
      </Button>
    </nav>
  );
}

function App() {
  return (
    <>
      <Toaster richColors position="bottom-right" />
      <Nav />
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/clusters" element={<ClustersPage />} />
        <Route path="/clusters/:clusterId" element={<ClusterDetailPage />} />
        <Route path="/jobs" element={<JobsPage />} />
        <Route path="/jobs/new" element={<JobSubmitPage />} />
        <Route path="/jobs/:jobId" element={<JobDetailPage />} />
        <Route path="/admin" element={<AdminLayout />}>
          <Route index element={<Navigate to="institutes" replace />} />
          <Route path="institutes" element={<AdminInstitutesPage />} />
          <Route path="clients" element={<AdminClientsPage />} />
          <Route path="quotas" element={<AdminQuotasPage />} />
          <Route path="reservations" element={<AdminReservationsPage />} />
        </Route>
      </Routes>
    </>
  );
}

export default App;
