import { Navigate, Outlet } from 'react-router-dom'
import { isAuthenticated } from '../../lib/api.js'
import Sidebar from './Sidebar.jsx'
import Header from './Header.jsx'

export default function Shell() {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />
  }

  return (
    <div className="flex h-screen overflow-hidden bg-surface-page">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Header />
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
