import { useState } from 'react'
import { BrowserRouter, Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { Menu, X } from 'lucide-react'
import { StoreProvider } from './store/store'
import { Logo, Sidebar } from './components/layout/Sidebar'
import { ToastHost } from './components/ui/ToastHost'
import { BackgroundField } from './components/ui/BackgroundField'
import { HomePage } from './pages/Home'
import { WorkspacePage } from './pages/Workspace'
import { NewExperimentPage } from './pages/NewExperiment'
import { ExperimentsPage } from './pages/Experiments'
import { AgentsPage } from './pages/Agents'
import { EvidencePage } from './pages/Evidence'
import { MemoryPage } from './pages/Memory'
import { DatasetsPage } from './pages/Datasets'
import { ModelsPage } from './pages/Models'
import { SettingsPage } from './pages/Settings'

function AppLayout() {
  const [mobileNav, setMobileNav] = useState(false)
  const [collapsed, setCollapsed] = useState(() => {
    if (typeof window === 'undefined') return false
    return window.localStorage.getItem('as-sidebar-collapsed') === '1'
  })

  const toggleCollapsed = () => {
    setCollapsed((c) => {
      const next = !c
      window.localStorage.setItem('as-sidebar-collapsed', next ? '1' : '0')
      return next
    })
  }

  return (
    <div className="flex h-full w-full">
      <div className="hidden md:flex">
        <Sidebar collapsed={collapsed} onToggle={toggleCollapsed} />
      </div>

      {mobileNav && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-ink-950/70" onClick={() => setMobileNav(false)} />
          <div className="anim-slide-right absolute inset-y-0 left-0">
            <div className="relative">
              <button
                onClick={() => setMobileNav(false)}
                className="absolute top-3.5 right-3 z-10 rounded-sm p-1 text-paper-400 hover:text-paper-100"
                aria-label="Close navigation"
              >
                <X size={15} />
              </button>
              <div onClick={() => setMobileNav(false)}>
                <Sidebar />
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="flex h-full min-w-0 flex-1 flex-col">
        <div className="flex h-[46px] shrink-0 items-center justify-between border-b border-ink-600 bg-ink-950/80 px-3 backdrop-blur-md md:hidden">
          <button
            onClick={() => setMobileNav(true)}
            className="rounded-sm p-1.5 text-paper-300 hover:bg-ink-850 hover:text-paper-100"
            aria-label="Open navigation"
          >
            <Menu size={16} />
          </button>
          <Logo compact />
          <span className="w-6" />
        </div>

        <main className="min-h-0 flex-1 overflow-hidden">
          <div className="h-full min-h-0">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <StoreProvider>
      <BrowserRouter>
        <div className="relative h-full w-full">
          <BackgroundField />
          <div className="relative z-10 h-full">
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route element={<AppLayout />}>
                <Route path="/workspace" element={<WorkspacePage />} />
                <Route path="/new" element={<NewExperimentPage />} />
                <Route path="/experiments" element={<ExperimentsPage />} />
                <Route path="/agents" element={<AgentsPage />} />
                <Route path="/evidence" element={<EvidencePage />} />
                <Route path="/memory" element={<MemoryPage />} />
                <Route path="/datasets" element={<DatasetsPage />} />
                <Route path="/models" element={<ModelsPage />} />
                <Route path="/settings" element={<SettingsPage />} />
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </div>
          <ToastHost />
        </div>
      </BrowserRouter>
    </StoreProvider>
  )
}
