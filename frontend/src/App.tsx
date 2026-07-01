import { Suspense, lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell, AppShellLoadingFallback } from "./components/AppShell";

const HomePage = lazy(() =>
  import("./pages/HomePage").then((module) => ({ default: module.HomePage })),
);
const AuthPage = lazy(() =>
  import("./pages/AuthPage").then((module) => ({ default: module.AuthPage })),
);
const ParcelRequestPage = lazy(() =>
  import("./pages/ParcelRequestPage").then((module) => ({
    default: module.ParcelRequestPage,
  })),
);
const RideRequestPage = lazy(() =>
  import("./pages/RideRequestPage").then((module) => ({
    default: module.RideRequestPage,
  })),
);
const CaptainCornerPage = lazy(() =>
  import("./pages/CaptainCornerPage").then((module) => ({
    default: module.CaptainCornerPage,
  })),
);
const LiveMapPage = lazy(() =>
  import("./pages/LiveMapPage").then((module) => ({ default: module.LiveMapPage })),
);
const DashboardPage = lazy(() =>
  import("./pages/DashboardPage").then((module) => ({
    default: module.DashboardPage,
  })),
);
const ProfilePage = lazy(() =>
  import("./pages/ProfilePage").then((module) => ({ default: module.ProfilePage })),
);

function App() {
  return (
    <Suspense fallback={<AppShellLoadingFallback />}>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/auth" element={<AuthPage />} />
          <Route path="/parcel" element={<ParcelRequestPage />} />
          <Route path="/ride" element={<RideRequestPage />} />
          <Route path="/captain" element={<CaptainCornerPage />} />
          <Route path="/map" element={<LiveMapPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </Suspense>
  );
}

export default App;
