import { NavLink, Route, Routes } from "react-router-dom";
import { ClustersPage } from "@/pages/ClustersPage";
import { ClusterDetailPage } from "@/pages/ClusterDetailPage";
import { JobsPage } from "@/pages/JobsPage";
import { JobSubmitPage } from "@/pages/JobSubmitPage";
import { JobDetailPage } from "@/pages/JobDetailPage";

function Nav() {
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-2 rounded-md text-sm font-medium ${isActive ? "bg-secondary" : "text-muted-foreground hover:bg-secondary/50"}`;

  return (
    <nav className="border-b flex gap-1 px-4 py-2">
      <NavLink to="/clusters" className={linkClass}>
        Clusters
      </NavLink>
      <NavLink to="/jobs" className={linkClass}>
        Jobs
      </NavLink>
      {/* Admin (#67) lands here once that ticket is built. */}
    </nav>
  );
}

function App() {
  return (
    <>
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
