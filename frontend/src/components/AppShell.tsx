import { AlertCircle, LocateFixed, RotateCcw, Sparkles, X } from "lucide-react";
import { useMemo, useTransition } from "react";
import { Outlet, useLocation } from "react-router-dom";

import { useRouteFusion } from "../context/RouteFusionContext";
import { createLiveMapScenario } from "../lib/mapScenario";
import { LiveMapCanvas } from "./LiveMapCanvas";
import { TopNav } from "./TopNav";

const mapRoutes = new Set(["/parcel", "/ride", "/captain", "/map"]);
const clearActionRoutes = new Set(["/parcel", "/ride", "/captain", "/map"]);

export function AppShell() {
  const {
    error,
    bannerMessage,
    locationToast,
    clearBanner,
    clearLocationToast,
    clearRequests,
    mapScenario,
    recommendation,
    currentLocation,
  } = useRouteFusion();
  const location = useLocation();
  const showMap = mapRoutes.has(location.pathname);
  const showClearAction = clearActionRoutes.has(location.pathname);
  const [isPending, startTransition] = useTransition();
  const isClearBanner = bannerMessage?.toLowerCase().includes("cleared") ?? false;
  const visibleBannerMessage = !showClearAction && isClearBanner ? null : bannerMessage;

  const activeScenario = useMemo(() => {
    if (!showMap) {
      return null;
    }

    if (mapScenario) {
      return mapScenario;
    }

    return createLiveMapScenario(recommendation, currentLocation);
  }, [currentLocation, mapScenario, recommendation, showMap]);

  return (
    <div className="min-h-screen bg-[#f8f9fa] text-[#111827]">
      <TopNav />
      <main className="mx-auto max-w-[1600px] px-4 pb-4 pt-4 sm:px-6 lg:px-8">
        <div
          className={`grid gap-4 ${
            showMap ? "lg:h-[calc(100vh-108px)] lg:grid-cols-[minmax(360px,440px)_minmax(0,1fr)]" : "lg:grid-cols-1"
          }`}
        >
          {showMap ? (
            <section
              className="flex min-h-[480px] flex-col overflow-hidden rounded-[32px] border border-[#e7eaee] bg-white shadow-[0_25px_60px_rgba(15,23,42,0.08)] order-2 lg:order-1 lg:min-h-0"
            >
              {showClearAction ? (
                <div className="border-b border-[#eef1f4] px-6 py-4">
                  <div className="flex flex-wrap items-center gap-3 text-sm">
                    <button
                      type="button"
                      onClick={() => {
                        startTransition(() => {
                          void clearRequests();
                        });
                      }}
                      className="inline-flex items-center gap-2 rounded-full bg-[#111111] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[#000000]"
                    >
                      <RotateCcw className={`h-4 w-4 ${isPending ? "animate-spin" : ""}`} />
                      {isPending ? "Clearing..." : "Clear Requests"}
                    </button>
                  </div>
                </div>
              ) : null}

              {locationToast ? (
                <div className="border-b border-[#eef1f4] px-6 py-4">
                  <div className="flex items-start justify-between gap-4 rounded-[22px] bg-[#fff7ed] px-4 py-3 text-sm text-[#9a3412]">
                    <div className="flex items-center gap-2">
                      <LocateFixed className="h-4 w-4" />
                      <span>{locationToast}</span>
                    </div>
                    <button
                      type="button"
                      onClick={clearLocationToast}
                      className="text-[#c2410c] transition hover:text-[#7c2d12]"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              ) : null}

              {visibleBannerMessage ? (
                <div className="border-b border-[#eef1f4] px-6 py-4">
                  <div className="flex items-start justify-between gap-4 rounded-[22px] bg-[#f5f7ff] px-4 py-3 text-sm text-[#4338ca]">
                    <div className="flex items-center gap-2">
                      <Sparkles className="h-4 w-4" />
                      <span>{visibleBannerMessage}</span>
                    </div>
                    <button type="button" onClick={clearBanner} className="text-[#6b7280] transition hover:text-[#111827]">
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              ) : null}

              {error ? (
                <div className="border-b border-[#eef1f4] px-6 py-4">
                  <div className="flex items-center gap-2 rounded-[22px] bg-[#fff1f2] px-4 py-3 text-sm text-[#b42318]">
                    <AlertCircle className="h-4 w-4" />
                    {error}
                  </div>
                </div>
              ) : null}

              <div className="no-scrollbar flex-1 overflow-y-auto">
                <Outlet />
              </div>
            </section>
          ) : (
            <div className="order-1">
              {locationToast ? (
                <div className="mb-3 rounded-[22px] bg-[#fff7ed] px-4 py-3 text-sm text-[#9a3412] flex items-start justify-between gap-4">
                  <div className="flex items-center gap-2">
                    <LocateFixed className="h-4 w-4" />
                    <span>{locationToast}</span>
                  </div>
                  <button type="button" onClick={clearLocationToast} className="text-[#c2410c] transition hover:text-[#7c2d12]">
                    <X className="h-4 w-4" />
                  </button>
                </div>
              ) : null}

              {visibleBannerMessage ? (
                <div className="mb-3 rounded-[22px] bg-[#f5f7ff] px-4 py-3 text-sm text-[#4338ca] flex items-start justify-between gap-4">
                  <div className="flex items-center gap-2">
                    <Sparkles className="h-4 w-4" />
                    <span>{visibleBannerMessage}</span>
                  </div>
                  <button type="button" onClick={clearBanner} className="text-[#6b7280] transition hover:text-[#111827]">
                    <X className="h-4 w-4" />
                  </button>
                </div>
              ) : null}

              {error ? (
                <div className="mb-3 rounded-[22px] bg-[#fff1f2] px-4 py-3 text-sm text-[#b42318] flex items-center gap-2">
                  <AlertCircle className="h-4 w-4" />
                  {error}
                </div>
              ) : null}

              <Outlet />
            </div>
          )}

          {showMap && activeScenario ? (
            <aside className="order-1 min-h-[44vh] lg:order-2 lg:h-full lg:min-h-0">
              <LiveMapCanvas scenario={activeScenario} />
            </aside>
          ) : null}
        </div>
      </main>
    </div>
  );
}
