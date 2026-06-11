import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { ToastProvider } from './context/ToastContext.jsx'
import Shell from './components/layout/Shell.jsx'
import LoginPage from './pages/LoginPage.jsx'
import OverviewPage from './pages/OverviewPage.jsx'
import NodesPage from './pages/NodesPage.jsx'
import NodeDetailPage from './pages/NodeDetailPage.jsx'
import AddVmPage from './pages/AddVmPage.jsx'
import JobsPage from './pages/JobsPage.jsx'
import CompliancePage from './pages/CompliancePage.jsx'
import PuppetRulesPage from './pages/PuppetRulesPage.jsx'
import ApiKeysPage from './pages/ApiKeysPage.jsx'
import AuditLogPage from './pages/AuditLogPage.jsx'
import InfrastructurePage from './pages/InfrastructurePage.jsx'
import UsersPage from './pages/UsersPage.jsx'
import UserGroupsPage from './pages/UserGroupsPage.jsx'
import PermissionsPage from './pages/PermissionsPage.jsx'

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
            <Route path="/add-vm" element={<AddVmPage />} />
            <Route path="/infrastructure" element={<InfrastructurePage />} />
            <Route path="/jobs" element={<JobsPage />} />
            <Route path="/compliance" element={<CompliancePage />} />
            <Route path="/rules" element={<PuppetRulesPage />} />
            <Route path="/keys" element={<ApiKeysPage />} />
            <Route path="/audit" element={<AuditLogPage />} />
            {/* IAM routes */}
            <Route path="/iam/users" element={<UsersPage />} />
            <Route path="/iam/groups" element={<UserGroupsPage />} />
            <Route path="/iam/keys" element={<ApiKeysPage />} />
            <Route path="/iam/permissions" element={<PermissionsPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/overview" replace />} />
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  )
}
