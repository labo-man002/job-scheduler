export default function App() {
  return (
    <main style={{ fontFamily: "sans-serif", padding: "24px" }}>
      <h1>Slurm Observability</h1>
      <p>Operator-first, observability-first UI for Slurm clusters.</p>

      <section style={{ marginTop: "24px" }}>
        <h2>MVP Hero Surface Placeholder</h2>
        <ul>
          <li>Top summary bar</li>
          <li>Left queue / filter panel</li>
          <li>Center topology surface</li>
          <li>Right drilldown panel</li>
          <li>Bottom insights panel</li>
        </ul>
      </section>

      <section style={{ marginTop: "24px" }}>
        <p>
          See <code>docs/mvp-doc.md</code> and <code>docs/repo-plan.md</code> for
          the current product and implementation direction.
        </p>
      </section>
    </main>
  );
}
