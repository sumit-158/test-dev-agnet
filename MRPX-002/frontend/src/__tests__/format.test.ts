import { ApiError, ERROR_UNAVAILABLE, fetchCandidates, fetchFilters } from "../api";
import { daysOld, formatDate, formatMonth, formatQty } from "../format";

afterEach(() => {
  vi.unstubAllGlobals();
});

test("f05 ac1 formatQty groups and trims", () => {
  expect(formatQty(336233)).toBe("336,233");
  expect(formatQty(2035876.5)).toBe("2,035,876.5");
  expect(formatQty(0)).toBe("0");
});

test("f05 ac2 dates", () => {
  expect(formatDate("2026-08-30")).toBe("30 Aug 2026");
  expect(formatMonth("202608")).toBe("Aug 2026");
  expect(daysOld("2026-08-30", new Date("2026-11-11T08:00:00Z"))).toBe(73);
});

test("f05 ac3 query string", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: () => ({
      items: [],
      total: 0,
      mrp_snapshot_date: null,
      inventory_month: null,
      limit: 50,
      offset: 0,
    }),
  });
  vi.stubGlobal("fetch", fetchMock);

  await fetchCandidates({ shortPlant: ["3300"], criticality: ["A", "NONE"] });

  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(fetchMock.mock.calls[0][0]).toBe(
    "/api/transfer-candidates?short_plant=3300&criticality=A&criticality=NONE" +
      "&sort_by=movable_qty&sort_dir=desc&limit=50&offset=0",
  );
});

test("f05 ac4 api error", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: false,
    status: 503,
    json: () => {
      throw new Error();
    },
  });
  vi.stubGlobal("fetch", fetchMock);

  const error = await fetchFilters().catch((e: unknown) => e);

  expect(error).toBeInstanceOf(ApiError);
  expect((error as ApiError).status).toBe(503);
  expect((error as ApiError).detail).toBe(ERROR_UNAVAILABLE);
});
