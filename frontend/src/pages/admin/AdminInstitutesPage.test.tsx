import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AdminInstitutesPage } from "./AdminInstitutesPage";
import { api } from "@/api/client";

vi.mock("@/api/client", () => ({
  api: { GET: vi.fn(), POST: vi.fn() },
}));

function renderPage() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <AdminInstitutesPage />
    </QueryClientProvider>,
  );
}

describe("AdminInstitutesPage", () => {
  beforeEach(() => {
    vi.mocked(api.GET).mockReset().mockResolvedValue({
      data: [{ institute_id: 1, institute_name: "Existing Institute" }],
      error: undefined,
      response: new Response(),
    } as never);
    vi.mocked(api.POST).mockReset();
  });

  it("lists existing institutes", async () => {
    renderPage();
    expect(await screen.findByText("Existing Institute")).toBeInTheDocument();
  });

  it("disables Register until a name is entered", async () => {
    renderPage();
    await screen.findByText("Existing Institute");
    expect(screen.getByRole("button", { name: /register/i })).toBeDisabled();

    await userEvent.type(screen.getByPlaceholderText("Institute name"), "New Institute");
    expect(screen.getByRole("button", { name: /register/i })).not.toBeDisabled();
  });

  it("submits the name and refreshes the list on success", async () => {
    vi.mocked(api.POST).mockResolvedValue({
      data: { detail: "Institute registered", status_code: 201, institute_id: 2, institute_name: "New Institute" },
      error: undefined,
      response: new Response(),
    } as never);

    renderPage();
    await screen.findByText("Existing Institute");
    await userEvent.type(screen.getByPlaceholderText("Institute name"), "New Institute");
    await userEvent.click(screen.getByRole("button", { name: /register/i }));

    expect(api.POST).toHaveBeenCalledWith("/institutes", { body: { institute_name: "New Institute" } });
    // The input clears back to the empty/disabled state on success.
    expect(await screen.findByRole("button", { name: /register/i })).toBeDisabled();
  });
});
