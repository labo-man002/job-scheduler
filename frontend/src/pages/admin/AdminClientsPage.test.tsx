import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AdminClientsPage } from "./AdminClientsPage";
import { api } from "@/api/client";

vi.mock("@/api/client", () => ({
  api: { GET: vi.fn(), POST: vi.fn() },
}));

const INSTITUTES = [{ institute_id: 1, institute_name: "Institute One" }];
const CLIENTS = [{ client_id: 10, owner: "alice", institute_id: 1, client_status: "ONLINE" }];

function mockGet() {
  vi.mocked(api.GET)
    .mockReset()
    .mockImplementation(((path: string) => {
      if (path === "/institutes") return Promise.resolve({ data: INSTITUTES, error: undefined, response: new Response() });
      if (path === "/clients") return Promise.resolve({ data: CLIENTS, error: undefined, response: new Response() });
      throw new Error(`unexpected path ${path}`);
    }) as typeof api.GET);
}

function renderPage() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <AdminClientsPage />
    </QueryClientProvider>,
  );
}

describe("AdminClientsPage", () => {
  beforeEach(() => {
    mockGet();
    vi.mocked(api.POST).mockReset();
  });

  it("lists clients with their resolved institute name", async () => {
    renderPage();
    const owner = await screen.findByText("alice");
    // "Institute One" alone would also match the <option> elements in the selects --
    // check the whole list item (which has both pieces) instead of that text in isolation.
    expect(owner.closest("li")?.textContent).toMatch(/Institute One/);
  });

  it("shows an ONLINE client's status badge", async () => {
    renderPage();
    const owner = await screen.findByText("alice");
    expect(owner.closest("li")?.textContent).toMatch(/Online/);
  });

  it("requires both an owner name and an institute before registering", async () => {
    renderPage();
    await screen.findByText("alice");
    const registerButton = screen.getByRole("button", { name: /register/i });
    expect(registerButton).toBeDisabled();

    await userEvent.type(screen.getByPlaceholderText("Owner name"), "bob");
    expect(registerButton).toBeDisabled(); // owner alone isn't enough -- still needs an institute

    await userEvent.selectOptions(screen.getByLabelText("Institute"), "1");
    expect(registerButton).not.toBeDisabled();
  });

  it("submits owner + institute_id together", async () => {
    vi.mocked(api.POST).mockResolvedValue({
      data: { detail: "ok", status_code: 201, client_id: 11, owner: "bob", institute_id: 1, client_status: "OFFLINE" },
      error: undefined,
      response: new Response(),
    } as never);

    renderPage();
    await screen.findByText("alice");
    await userEvent.type(screen.getByPlaceholderText("Owner name"), "bob");
    await userEvent.selectOptions(screen.getByLabelText("Institute"), "1");
    await userEvent.click(screen.getByRole("button", { name: /register/i }));

    expect(api.POST).toHaveBeenCalledWith("/clients", { body: { owner: "bob", institute_id: 1 } });
  });
});
