import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import App from "./App";

function renderApp(initialPath = "/") {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("App", () => {
  it("renders the nav", () => {
    // Navigate to /clusters explicitly rather than relying on "/" happening to
    // render ClustersPage -- the root route can change out from under this test
    // otherwise. "Clusters" legitimately appears twice on this route: the nav
    // link and the page's own heading (which stays visible even while loading).
    renderApp("/clusters");
    expect(screen.getByRole("link", { name: "Clusters" })).toBeInTheDocument();
  });
});
