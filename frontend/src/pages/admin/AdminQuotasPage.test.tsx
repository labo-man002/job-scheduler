import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AdminQuotasPage } from "./AdminQuotasPage";
import { api } from "@/api/client";

vi.mock("@/api/client", () => ({
  api: { GET: vi.fn(), POST: vi.fn(), DELETE: vi.fn() },
}));

const INSTITUTES = [{ institute_id: 1, institute_name: "Institute One" }];
const QUOTAS = [{ id: 5, institute_id: 1, resource_type: "CPU", limit: 100, period: "2026-08-01T00:00:00Z" }];

function mockGet(quotas: unknown[] = QUOTAS) {
  vi.mocked(api.GET)
    .mockReset()
    .mockImplementation(((path: string) => {
      if (path === "/institutes") return Promise.resolve({ data: INSTITUTES, error: undefined, response: new Response() });
      if (path === "/quotas") return Promise.resolve({ data: quotas, error: undefined, response: new Response() });
      throw new Error(`unexpected path ${path}`);
    }) as typeof api.GET);
}

function renderPage() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <AdminQuotasPage />
    </QueryClientProvider>,
  );
}

describe("AdminQuotasPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockGet();
    vi.mocked(api.POST).mockReset();
    vi.mocked(api.DELETE).mockReset();
  });

  it("lists existing quotas with the resolved institute name", async () => {
    renderPage();
    // "Institute One" alone would also match the <option> elements in the selects above --
    // check the whole list item (which has both pieces) instead of that text in isolation.
    const deleteButton = await screen.findByRole("button", { name: /delete quota/i });
    expect(deleteButton.closest("li")?.textContent).toMatch(/Institute One/);
  });

  it("rejects a fractional limit without calling the API", async () => {
    renderPage();
    await screen.findByRole("button", { name: /delete quota/i }); // wait for the quota list to load
    await userEvent.selectOptions(screen.getByLabelText("Institute"), "1");

    const limitInput = screen.getByLabelText("Limit");
    await userEvent.clear(limitInput);
    await userEvent.type(limitInput, "10.5");

    expect(screen.getByRole("button", { name: /set quota/i })).toBeDisabled();
    expect(api.POST).not.toHaveBeenCalled();
  });

  it("deletes a quota after confirming", async () => {
    vi.mocked(api.DELETE).mockResolvedValue({ data: { detail: "ok", status_code: 200 }, error: undefined, response: new Response() } as never);
    vi.spyOn(window, "confirm").mockReturnValue(true);

    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: /delete quota/i }));

    expect(api.DELETE).toHaveBeenCalledWith("/quotas/{quota_id}", { params: { path: { quota_id: 5 } } });
  });

  it("does not delete when the confirmation is cancelled", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);

    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: /delete quota/i }));

    expect(api.DELETE).not.toHaveBeenCalled();
  });
});
