import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { CaptainCornerPage } from "./pages/CaptainCornerPage";
import { DashboardPage } from "./pages/DashboardPage";
import { HomePage } from "./pages/HomePage";

import { AuthPage } from "./pages/AuthPage";
import { ParcelRequestPage } from "./pages/ParcelRequestPage";
import { ProfilePage } from "./pages/ProfilePage";
import { RideRequestPage } from "./pages/RideRequestPage";

function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/auth" element={<AuthPage />} />
        <Route path="/parcel" element={<ParcelRequestPage />} />
        <Route path="/ride" element={<RideRequestPage />} />
        <Route path="/captain" element={<CaptainCornerPage />} />

        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

export default App;
