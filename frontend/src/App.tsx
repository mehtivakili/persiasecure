import { Navigate, Route, Routes } from "react-router-dom";

import { useAppSelector } from "./app/hooks";
import { featureEnabled } from "./config/features";

import AppLayout from "./components/AppLayout";
import RequireAuth from "./components/RequireAuth";
import CamerasPage from "./features/cameras/CamerasPage";
import DashboardPage from "./features/dashboard/DashboardPage";
import EventsPage from "./features/events/EventsPage";
import LiveViewPage from "./features/liveview/LiveViewPage";
import LoginPage from "./features/auth/LoginPage";
import PlaybackPage from "./features/playback/PlaybackPage";
import ExportsPage from "./features/exports/ExportsPage";
import RolesPage from "./features/users/RolesPage";
import UsersPage from "./features/users/UsersPage";
import AnalyticsPage from "./features/analytics/AnalyticsPage";
import AccessPage from "./features/access/AccessPage";
import MapsPage from "./features/maps/MapsPage";
import FederationPage from "./features/federation/FederationPage";
import EvidencePage from "./features/evidence/EvidencePage";
import AutomationPage from "./features/automation/AutomationPage";
import ReportsPage from "./features/reports/ReportsPage";
import HealthPage from "./features/health/HealthPage";
import SettingsPage from "./features/settings/SettingsPage";
import SmartDeskPage from "./features/desk/SmartDeskPage";

export default function App() {
  const user = useAppSelector((s) => s.auth.user);

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route path="/" element={<DashboardPage />} />
        <Route path="/desk" element={<SmartDeskPage />} />
        <Route path="/live" element={<LiveViewPage />} />
        <Route path="/playback" element={<PlaybackPage />} />
        <Route path="/exports" element={<ExportsPage />} />
        <Route path="/cameras" element={<CamerasPage />} />
        {featureEnabled(user, "analytics") && <Route path="/analytics" element={<AnalyticsPage />} />}
        {featureEnabled(user, "access_control") && <Route path="/access" element={<AccessPage />} />}
        {featureEnabled(user, "maps") && <Route path="/maps" element={<MapsPage />} />}
        {featureEnabled(user, "federation") && <Route path="/federation" element={<FederationPage />} />}
        {featureEnabled(user, "evidence") && <Route path="/evidence" element={<EvidencePage />} />}
        <Route path="/automation" element={<AutomationPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/health" element={<HealthPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/events" element={<EventsPage />} />
        <Route path="/users" element={<UsersPage />} />
        <Route path="/roles" element={<RolesPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
