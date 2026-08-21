import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import App from "./App";

function renderApp() {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("App", () => {
  it("renders the nav", () => {
    renderApp();
    // "Clusters" now legitimately appears twice -- the nav link and the page's own
    // heading (which stays visible even while the page is loading, unlike before).
    expect(screen.getByRole("link", { name: "Clusters" })).toBeInTheDocument();
  });
});
