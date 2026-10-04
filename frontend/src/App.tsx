import { useState } from 'react'
import { BrowserRouter, Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import { Menu, X } from 'lucide-react'
import { StoreProvider, useStore } from './store/store'
import { Logo, Sidebar } from './components/layout/Sidebar'
import { ToastHost } from './components/ui/ToastHost'
import { BackgroundField } from './components/ui/BackgroundField'
import { ThemeProvider } from './components/ui/ThemeProvider'
import { ThemeToggle } from './components/ui/ThemeToggle'
import { LenisProvider } from './components/anim/LenisProvider'
import { CustomCursor } from './components/anim/CustomCursor'
import { ScrollProgressBar } from './components/anim/ScrollProgressBar'
import { PageTransition } from './components/anim/PageTransition'
import { Preloader } from './components/anim/Preloader'
import { HomePage } from './pages/Home'
import { WorkspacePage } from './pages/Workspace'
import { NewExperimentPage } from './pages/NewExperiment'
import { ExperimentsPage } from './pages/Experiments'
import { AgentsPage } from './pages/Agents'
import { EvidencePage } from './pages/Evidence'
import { MemoryPage } from './pages/Memory'
import { CheckLLMPage } from './pages/CheckLLM'
import { DatasetsPage } from './pages/Datasets'
import { ModelsPage } from './pages/Models'
import { SettingsPage } from './pages/Settings'
import { LoginPage } from './pages/Login'
import { SandboxPage } from './pages/Sandbox'

function ProtectedRoute() {
  const { authReady, user } = useStore()
  if (!authReady) {
    return (
      <div className="flex h-full w-full items-center justify-center" style={{ color: 'var(--as-text-3)' }}>
        <div className="flex flex-col items-center gap-4">
          <svg className="anim-spin-slow" width="32" height="32" viewBox="0 0 32 32" fill="none" aria-hidden>
            <circle cx="16" cy="16" r="12" stroke="var(--as-border)" strokeWidth="2.5" />
            <circle cx="16" cy="16" r="12" stroke="var(--as-accent)" strokeWidth="2.5"
              strokeDasharray="22 54" strokeLinecap="round" />
          </svg>
          <span className="mono text-[12.5px] tracking-widest uppercase" style={{ color: 'var(--as-text-3)' }}>
            Connecting…
          </span>
        </div>
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace />
  return <Outlet />
}

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
          <div
            className="absolute inset-0"
            style={{ background: 'rgba(6,7,13,0.75)', backdropFilter: 'blur(4px)' }}
            onClick={() => setMobileNav(false)}
          />
          <div className="anim-slide-right absolute inset-y-0 left-0">
            <div className="relative">
              <button
                onClick={() => setMobileNav(false)}
                className="absolute top-3.5 right-3 z-10 rounded-lg p-1.5"
                style={{ color: 'var(--as-text-2)' }}
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
        <div
          className="glass flex h-[52px] shrink-0 items-center justify-between border-b px-4 md:hidden"
          style={{ borderColor: 'var(--as-border)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)' }}
        >
          <button onClick={() => setMobileNav(true)} className="rounded-xl p-2 transition-colors"
            style={{ color: 'var(--as-text-2)' }} aria-label="Open navigation">
            <Menu size={16} />
          </button>
          <Logo compact />
          <ThemeToggle />
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

/** Inner router with AnimatePresence for page transitions */
function AnimatedRoutes() {
  const location = useLocation()
  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        {/* Public */}
        <Route path="/" element={<PageTransition><HomePage /></PageTransition>} />
        <Route path="/login" element={<PageTransition><LoginPage /></PageTransition>} />

        {/* Protected */}
        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            <Route path="/workspace"   element={<PageTransition><WorkspacePage /></PageTransition>} />
            <Route path="/new"         element={<PageTransition><NewExperimentPage /></PageTransition>} />
            <Route path="/experiments" element={<PageTransition><ExperimentsPage /></PageTransition>} />
            <Route path="/agents"      element={<PageTransition><AgentsPage /></PageTransition>} />
            <Route path="/evidence"    element={<PageTransition><EvidencePage /></PageTransition>} />
            <Route path="/memory"      element={<PageTransition><MemoryPage /></PageTransition>} />
            <Route path="/checkllm"   element={<PageTransition><CheckLLMPage /></PageTransition>} />
            <Route path="/datasets"    element={<PageTransition><DatasetsPage /></PageTransition>} />
            <Route path="/models"      element={<PageTransition><ModelsPage /></PageTransition>} />
            <Route path="/settings"    element={<PageTransition><SettingsPage /></PageTransition>} />
            <Route path="/sandbox"     element={<PageTransition><SandboxPage /></PageTransition>} />
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AnimatePresence>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <LenisProvider>
        <StoreProvider>
          <BrowserRouter>
            <Preloader />
            <CustomCursor />
            <ScrollProgressBar />
            <div className="relative h-full w-full">
              <BackgroundField />
              <div className="relative z-10 h-full">
                <AnimatedRoutes />
              </div>
              <ToastHost />
            </div>
          </BrowserRouter>
        </StoreProvider>
      </LenisProvider>
    </ThemeProvider>
  )
}
