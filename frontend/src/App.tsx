import { NavLink, Route, Routes } from "react-router-dom";
import { Network, Boxes, ListTodo, Moon, Sun } from "lucide-react";
import { Toaster } from "sonner";
import { ClustersPage } from "@/pages/ClustersPage";
import { ClusterDetailPage } from "@/pages/ClusterDetailPage";
import { JobsPage } from "@/pages/JobsPage";
import { JobSubmitPage } from "@/pages/JobSubmitPage";
import { JobDetailPage } from "@/pages/JobDetailPage";
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
      <NavLink to="/clusters" className={linkClass}>
        <Boxes className="size-4" />
        Clusters
      </NavLink>
      <NavLink to="/jobs" className={linkClass}>
        <ListTodo className="size-4" />
        Jobs
      </NavLink>
      {/* Admin (#67) lands here once that ticket is built. */}
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
        <Route path="/" element={<ClustersPage />} />
        <Route path="/clusters" element={<ClustersPage />} />
        <Route path="/clusters/:clusterId" element={<ClusterDetailPage />} />
        <Route path="/jobs" element={<JobsPage />} />
        <Route path="/jobs/new" element={<JobSubmitPage />} />
        <Route path="/jobs/:jobId" element={<JobDetailPage />} />
      </Routes>
    </>
  );
}

export default App;
