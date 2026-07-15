import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { ToastProvider } from './context/ToastContext.jsx'
import Shell from './components/layout/Shell.jsx'
import LoginPage from './pages/LoginPage.jsx'
import OverviewPage from './pages/OverviewPage.jsx'
import NodesPage from './pages/NodesPage.jsx'
import NodeDetailPage from './pages/NodeDetailPage.jsx'
import AddServerPage from './pages/AddServerPage.jsx'
import JobsPage from './pages/JobsPage.jsx'
import CompliancePage from './pages/CompliancePage.jsx'
import DetectionEventsPage from './pages/DetectionEventsPage.jsx'
import NodeCompliancePage from './pages/NodeCompliancePage.jsx'
import ProfilesPage from './pages/ProfilesPage.jsx'
import ProfileDetailPage from './pages/ProfileDetailPage.jsx'
import ApiKeysPage from './pages/ApiKeysPage.jsx'
import AuditLogPage from './pages/AuditLogPage.jsx'
import InfrastructurePage from './pages/InfrastructurePage.jsx'
import UsersPage from './pages/UsersPage.jsx'
import UserGroupsPage from './pages/UserGroupsPage.jsx'
import PermissionsPage from './pages/PermissionsPage.jsx'
import AccessControlPage from './pages/AccessControlPage.jsx'
import NodeGroupsPage from './pages/NodeGroupsPage.jsx'
import NodeGroupDetailPage from './pages/NodeGroupDetailPage.jsx'
import TiersPage from './pages/TiersPage.jsx'
import TlsCertificatePage from './pages/TlsCertificatePage.jsx'
import HelpPage from './pages/HelpPage.jsx'

export default function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<Shell />}>
            <Route index element={<Navigate to="/overview" replace />} />
            <Route path="/overview" element={<OverviewPage />} />
            <Route path="/nodes" element={<NodesPage />} />
            <Route path="/nodes/:id" element={<NodeDetailPage />} />
            <Route path="/add-server" element={<AddServerPage />} />
            <Route path="/infrastructure" element={<InfrastructurePage />} />
            <Route path="/jobs" element={<JobsPage />} />
            <Route path="/detection" element={<DetectionEventsPage />} />
            <Route path="/compliance" element={<CompliancePage />} />
            <Route path="/compliance/:id" element={<NodeCompliancePage />} />
            <Route path="/profiles" element={<ProfilesPage />} />
            <Route path="/profiles/:id" element={<ProfileDetailPage />} />
            <Route path="/tiers" element={<TiersPage />} />
            <Route path="/rules" element={<Navigate to="/profiles" replace />} />
            <Route path="/audit" element={<AuditLogPage />} />
            {/* Access Control — one page, four tabs */}
            <Route path="/iam" element={<AccessControlPage />}>
              <Route index element={<Navigate to="users" replace />} />
              <Route path="users" element={<UsersPage />} />
              <Route path="groups" element={<UserGroupsPage />} />
              <Route path="keys" element={<ApiKeysPage />} />
              <Route path="permissions" element={<PermissionsPage />} />
            </Route>
            {/* Back-compat redirects for the old standalone key route */}
            <Route path="/keys" element={<Navigate to="/iam/keys" replace />} />
            <Route path="/settings/tls" element={<TlsCertificatePage />} />
            {/* Node Groups */}
            <Route path="/node-groups" element={<NodeGroupsPage />} />
            <Route path="/node-groups/:id" element={<NodeGroupDetailPage />} />
            <Route path="/help" element={<HelpPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/overview" replace />} />
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  )
}
