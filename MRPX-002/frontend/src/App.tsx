import { Route, Routes } from "react-router-dom";

import TransferCandidatesPage from "./pages/TransferCandidatesPage";

// Placeholder: v2/F-07 replaces the detail route with MaterialDetailPage (under ./pages/).
export default function App() {
  return (
    <div className="min-h-screen bg-asm-paper text-asm-ink">
      <header className="flex h-14 items-center gap-3 bg-asm-navy px-6 text-white lg:h-14 max-lg:h-16">
        <span className="rounded-lg border-2 border-white px-2 py-1 text-sm font-bold tracking-wide">
          ASM
        </span>
        <span className="text-base font-semibold">Shortage rebalancing</span>
      </header>
      <main className="mx-auto max-w-[1400px] px-6 py-6">
        <Routes>
          <Route path="/" element={<TransferCandidatesPage />} />
          <Route
            path="/materials/:material/plants/:shortPlant"
            element={<div>Material detail</div>}
          />
        </Routes>
      </main>
    </div>
  );
}
