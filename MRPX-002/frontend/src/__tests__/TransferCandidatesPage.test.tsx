import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";

import * as api from "../api";
import TransferCandidatesPage from "../pages/TransferCandidatesPage";
import { samplePage, sampleFilters } from "./fixtures";

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.search}</div>;
}

function renderAt(url: string) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <TransferCandidatesPage />
      <LocationProbe />
    </MemoryRouter>,
  );
}

function firstBodyRow(): HTMLTableRowElement {
  const row = screen.getByRole("table").querySelector("tbody tr");
  if (!row) throw new Error("no body row");
  return row as HTMLTableRowElement;
}

beforeEach(() => {
  vi.spyOn(api, "fetchFilters").mockResolvedValue(sampleFilters);
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

test("f06 ac1 renders golden row first", async () => {
  const fetchCandidates = vi.spyOn(api, "fetchCandidates").mockResolvedValue(samplePage);
  renderAt("/?plant=3300");

  expect(await screen.findByText("3 transfer candidates for ASM Korea Ltd. (3300)")).toBeInTheDocument();
  expect(fetchCandidates).toHaveBeenCalledWith(
    expect.objectContaining({
      shortPlant: ["3300"],
      sortBy: "movable_qty",
      sortDir: "desc",
      limit: 50,
      offset: 0,
    }),
    expect.any(AbortSignal),
  );
  const row = firstBodyRow();
  expect(within(row).getByText("1236-561-01")).toBeInTheDocument();
  expect(row).toHaveTextContent("Criticality A");
  expect(row).toHaveTextContent("336,233");
  expect(row).toHaveTextContent("9 wk");
});

test("f06 ac2 freshness and stale warning", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(new Date("2026-11-11T08:00:00Z"));
  vi.spyOn(api, "fetchCandidates").mockResolvedValue(samplePage);
  renderAt("/?plant=3300");

  expect(
    await screen.findByText("MRP result 30 Aug 2026 · Inventory month Aug 2026"),
  ).toBeInTheDocument();
  expect(screen.getByText("73 days old")).toBeInTheDocument();
});

test("f06 ac3 empty state clears filters", async () => {
  vi.spyOn(api, "fetchCandidates").mockResolvedValue({ ...samplePage, items: [], total: 0 });
  renderAt("/?plant=3300&crit=A");

  expect(await screen.findByText("No transfer candidates match these filters.")).toBeInTheDocument();
  const empty = screen.getByRole("status");
  fireEvent.click(within(empty).getByRole("button", { name: "Clear filters" }));

  await waitFor(() =>
    expect(screen.getByTestId("location")).toHaveTextContent(/^\?sort=movable_qty&dir=desc&page=1$/),
  );
});

test("f06 ac4 error state retries", async () => {
  const fetchCandidates = vi
    .spyOn(api, "fetchCandidates")
    .mockRejectedValue(new api.ApiError(503, "The transfer candidates could not be loaded. Try again."));
  renderAt("/?plant=3300");

  expect(
    await screen.findByText("The transfer candidates could not be loaded. Try again."),
  ).toBeInTheDocument();
  expect(fetchCandidates).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));

  await waitFor(() => expect(fetchCandidates).toHaveBeenCalledTimes(2));
});
