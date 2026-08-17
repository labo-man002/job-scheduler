import { NavLink, Route, Routes } from "react-router-dom";
import { ClustersPage } from "@/pages/ClustersPage";

function Nav() {
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-2 rounded-md text-sm font-medium ${isActive ? "bg-secondary" : "text-muted-foreground hover:bg-secondary/50"}`;

  return (
    <nav className="border-b flex gap-1 px-4 py-2">
      <NavLink to="/clusters" className={linkClass}>
        Clusters
      </NavLink>
      {/* Jobs (#66) and Admin (#67) views land here once those tickets are built. */}
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
      </Routes>
    </>
  );
}

export default App;
