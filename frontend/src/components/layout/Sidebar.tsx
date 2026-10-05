import { useState, useEffect } from 'react'
import {
  Boxes,
  ChevronDown,
  Database,
  FlaskConical,
  LayoutGrid,
  Library,
  LogOut,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  PlugZap,
  ScrollText,
  Settings2,
  ShieldCheck,
  Sun,
  Terminal,
  User,
} from 'lucide-react'
import { NavLink } from 'react-router-dom'
import type { ComponentType } from 'react'
import { motion } from 'framer-motion'
import { useStore } from '../../store/context'
import { STAGE_META } from '../../data/experiments'
import { useTheme } from '../ui/ThemeProvider'
import { prefersReducedMotion } from '../../lib/animConfig'

type NavItem = {
  to: string
  label: string
  icon: ComponentType<{ size?: number; strokeWidth?: number; className?: string }>
}

const GROUPS: { title: string; items: NavItem[] }[] = [
  {
    title: 'Operate',
    items: [
      { to: '/workspace', label: 'Workspace', icon: LayoutGrid },
      { to: '/sandbox', label: 'Sandbox', icon: Terminal },
      { to: '/experiments', label: 'Experiments', icon: FlaskConical },
    ],
  },
  {
    title: 'Research',
    items: [
      { to: '/agents', label: 'Agents', icon: Boxes },
      { to: '/evidence', label: 'Evidence', icon: ShieldCheck },
      { to: '/memory', label: 'Memory', icon: Library },
      { to: '/checkllm', label: 'CheckLLM', icon: PlugZap },
    ],
  },
  {
    title: 'Assets',
    items: [
      { to: '/datasets', label: 'Datasets', icon: Database },
      { to: '/models', label: 'Models', icon: ScrollText },
    ],
  },
]

const SETTINGS: NavItem = { to: '/settings', label: 'Settings', icon: Settings2 }

const STATUS_TONE: Record<string, { dot: string; label: string }> = {
  CREATED:   { dot: 'bg-[var(--as-text-3)]',   label: 'created'   },
  QUEUED:    { dot: 'bg-[var(--as-warn)]',       label: 'queued'    },
  RUNNING:   { dot: 'bg-[var(--as-accent)]',     label: 'running'   },
  RETRYING:  { dot: 'bg-[var(--as-warn)]',       label: 'retrying'  },
  COMPLETED: { dot: 'bg-[var(--as-verify)]',     label: 'completed' },
  FAILED:    { dot: 'bg-[var(--as-error)]',      label: 'failed'    },
  CANCELLED: { dot: 'bg-[var(--as-text-3)]',     label: 'cancelled' },
}
const FALLBACK_TONE = { dot: 'bg-[var(--as-text-3)]', label: '—' }

export function Logo({ compact = false, hideName = false }: { compact?: boolean; hideName?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      {/* Logo mark — violet gradient */}
      <svg width="26" height="26" viewBox="0 0 32 32" aria-hidden className="shrink-0">
        <defs>
          <linearGradient id="logo-grad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#a78bfa"/>
            <stop offset="100%" stopColor="#2dd4bf"/>
          </linearGradient>
        </defs>
        <rect width="32" height="32" rx="9" fill="var(--as-glass-bg)" stroke="var(--as-border)"/>
        <path d="M8 22 L16 8 L24 22" stroke="url(#logo-grad)" strokeWidth="2.4" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M11.5 17.5 H20.5" stroke="url(#logo-grad)" strokeWidth="2.4" strokeLinecap="round"/>
        <circle cx="16" cy="25" r="1.5" fill="var(--as-teal)"/>
      </svg>
      {!hideName && (
        <span
          className={`font-semibold tracking-tight whitespace-nowrap transition-all duration-200 ${
            compact ? 'text-[15px]' : 'text-[15.5px]'
          }`}
          style={{ color: 'var(--as-text)' }}
        >
          AutoSage
        </span>
      )}
    </div>
  )
}

function NavItemRow({
  item,
  count,
  collapsed,
  onNavigate,
}: {
  item: NavItem
  count?: number
  collapsed: boolean
  onNavigate?: () => void
}) {
  const Icon = item.icon
  return (
    <NavLink
      to={item.to}
      title={collapsed ? item.label : undefined}
      onClick={onNavigate}
      className={({ isActive }) =>
        `group relative flex h-[34px] items-center gap-2.5 rounded-xl px-2.5 text-[14.5px] font-medium transition-all duration-150 overflow-visible ${
          collapsed ? 'justify-center px-0 w-[36px] mx-auto' : ''
        } ${
          isActive
            ? 'shadow-[0_0_12px_var(--as-accent-glow)]'
            : ''
        }`
      }
      style={({ isActive }) => ({
        background: isActive
          ? 'color-mix(in oklch, var(--as-accent) 15%, transparent)'
          : 'transparent',
        color: isActive ? 'var(--as-accent-hi)' : 'var(--as-text-2)',
      })}
    >
      {({ isActive }) => (
        <>
          <span className="relative shrink-0 flex items-center justify-center w-[18px] h-[18px]">
            <Icon
              size={16}
              strokeWidth={isActive ? 2 : 1.6}
              className={`transition-colors duration-150 ${
                isActive ? 'text-accent-400' : 'text-paper-400 group-hover:text-accent-300'
              }`}
            />
            {collapsed && count != null && count > 0 && (
              <span
                className="absolute -top-1 -right-1 h-[6px] w-[6px] rounded-full bg-accent-400 ring-2 ring-ink-950"
              />
            )}
          </span>
          <span
            className={`min-w-0 flex-1 overflow-hidden whitespace-nowrap transition-all duration-200 ${
              collapsed ? 'w-0 flex-none opacity-0' : 'opacity-100'
            }`}
          >
            {item.label}
          </span>
          {!collapsed && count != null && (
            <span
              className="mono shrink-0 text-[11px] transition-opacity duration-200"
              style={{ color: 'var(--as-text-3)' }}
            >
              {count}
            </span>
          )}
        </>
      )}
    </NavLink>
  )
}

function ThemeNavRow({ collapsed }: { collapsed: boolean }) {
  const { theme, toggle } = useTheme()
  const reduced = prefersReducedMotion()
  const isDark = theme === 'dark'
  return (
    <button
      onClick={toggle}
      role="switch"
      aria-checked={isDark}
      title={collapsed ? 'Toggle theme' : undefined}
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      className={`group relative flex h-[32px] w-full items-center gap-2.5 rounded-xl px-2.5 text-[15.5px] transition-colors duration-150 hover:bg-[var(--as-glass-bg)] active:scale-[0.98] ${
        collapsed ? 'justify-center px-0' : ''
      }`}
      style={{ color: 'var(--as-text-2)' }}
    >
      {!collapsed && (
        <span className="min-w-0 flex-1 overflow-hidden text-left whitespace-nowrap">
          Appearance
        </span>
      )}
      {/* Swipe switch */}
      <span
        aria-hidden
        className="relative h-[22px] w-[40px] shrink-0 rounded-full border transition-colors duration-300"
        style={{
          background: isDark
            ? 'color-mix(in oklch, var(--as-accent) 55%, transparent)'
            : 'var(--as-glass-bg)',
          borderColor: isDark ? 'var(--as-accent)' : 'var(--as-border-hi)',
          boxShadow: isDark ? '0 0 14px var(--as-accent-glow)' : 'none',
        }}
      >
        <motion.span
          className="absolute top-[2px] left-[2px] flex h-[16px] w-[16px] items-center justify-center rounded-full"
          style={{
            background: '#fff',
            color: isDark ? '#6d28d9' : '#d97706',
            boxShadow: '0 1px 4px rgba(0,0,0,0.4)',
          }}
          initial={false}
          animate={{ x: isDark ? 18 : 0 }}
          transition={
            reduced
              ? { duration: 0 }
              : { type: 'spring', stiffness: 550, damping: 32 }
          }
        >
          <span
            className="absolute inset-0 flex items-center justify-center transition-all duration-300"
            style={{ opacity: isDark ? 0 : 1, transform: isDark ? 'scale(0.5)' : 'scale(1)' }}
          >
            <Sun size={10} strokeWidth={2.4} />
          </span>
          <span
            className="absolute inset-0 flex items-center justify-center transition-all duration-300"
            style={{ opacity: isDark ? 1 : 0, transform: isDark ? 'scale(1)' : 'scale(0.5)' }}
          >
            <Moon size={10} strokeWidth={2.4} />
          </span>
        </motion.span>
      </span>
    </button>
  )
}

function GroupLabel({ title, collapsed }: { title: string; collapsed: boolean }) {
  return (
    <div
      className={`overflow-hidden px-2.5 pt-4 pb-1 transition-all duration-200 ${
        collapsed ? 'h-0 pt-0 pb-0 opacity-0' : 'opacity-100'
      }`}
    >
      <span className="label-xs whitespace-nowrap">{title}</span>
    </div>
  )
}

export function Sidebar({
  collapsed = false,
  onToggle,
  onNavigate,
}: {
  collapsed?: boolean
  onToggle?: () => void
  onNavigate?: () => void
}) {
  const { experiments, activeExperiment, elapsedLabel, memory, user, authError, logout } = useStore()
  const [userMenuOpen, setUserMenuOpen] = useState(false)

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (userMenuOpen && !(e.target as HTMLElement)?.closest('[aria-label="User menu"]')) {
        setUserMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [userMenuOpen])

  const agentCount = new Set(activeExperiment?.nodes.map((n) => n.agent) ?? []).size
  const counts: Record<string, number | undefined> = {
    '/experiments': experiments.length,
    '/agents': agentCount || STAGE_META.length,
    '/memory': memory.length,
    '/sandbox': 0,
  }

  const exp = activeExperiment
  const tone = STATUS_TONE[exp?.status ?? ''] ?? FALLBACK_TONE
  const totalStages = exp?.nodes.length ?? 9
  const doneStages = exp?.nodes.filter((n) => n.state === 'done').length ?? 0
  const progress =
    exp?.status === 'COMPLETED'
      ? 100
      : Math.round((doneStages / totalStages) * 100)
  const isLive = exp?.status === 'RUNNING' || exp?.status === 'QUEUED' || exp?.status === 'RETRYING'
  const userEmail = user?.email ?? (authError ? 'auth error' : '…')

  return (
    <aside
      className="group flex h-full shrink-0 flex-col overflow-hidden border-r transition-[width] duration-300 ease-in-out"
      style={{
        background: 'var(--as-glass-bg)',
        borderColor: 'var(--as-border)',
        backdropFilter: `blur(var(--as-glass-blur)) saturate(var(--as-glass-sat))`,
        WebkitBackdropFilter: `blur(var(--as-glass-blur)) saturate(var(--as-glass-sat))`,
        width: collapsed ? '60px' : '220px',
      }}
    >
      {/* ── Logo + collapse toggle ── */}
      <div
        className={`flex w-[220px] shrink-0 gap-2 px-3.5 pt-4 pb-3 ${
          collapsed ? 'flex-col items-start pb-2' : 'items-center'
        }`}
      >
        <NavLink to="/" className="min-w-0 shrink" onClick={onNavigate}>
          <Logo hideName={collapsed} />
        </NavLink>
        {onToggle && (
          <button
            onClick={onToggle}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-expanded={!collapsed}
            className={`rounded-xl p-1.5 transition-all duration-200 hover:bg-[var(--as-glass-bg-2)] focus-visible:opacity-100 ${
              collapsed ? 'opacity-0 group-hover:opacity-100' : 'ml-auto opacity-100'
            }`}
            style={{ color: 'var(--as-text-3)' }}
          >
            {collapsed ? <PanelLeftOpen size={14} /> : <PanelLeftClose size={14} />}
          </button>
        )}
      </div>

      {/* ── Navigation ── */}
      <nav className="flex w-[220px] shrink-0 flex-col gap-[2px] overflow-hidden px-2 pb-2">
        {GROUPS.map((g) => (
          <div key={g.title}>
            <GroupLabel title={g.title} collapsed={collapsed} />
            {g.items.map((it) => (
              <NavItemRow
                key={it.to}
                item={it}
                count={counts[it.to]}
                collapsed={collapsed}
                onNavigate={onNavigate}
              />
            ))}
          </div>
        ))}
        <div
          className="mt-2 border-t pt-2"
          style={{ borderColor: 'var(--as-border)' }}
        >
          <NavItemRow item={SETTINGS} collapsed={collapsed} onNavigate={onNavigate} />
          <ThemeNavRow collapsed={collapsed} />
        </div>
      </nav>

      {/* ── Engine status card ── */}
      <div className="mt-auto w-[220px] shrink-0 px-2.5 pt-3 pb-3">
        <div
          className="rounded-2xl border transition-all duration-300"
          style={{
            background: collapsed ? 'transparent' : 'color-mix(in oklch, var(--as-accent) 6%, var(--as-bg-2))',
            borderColor: collapsed ? 'transparent' : 'var(--as-border)',
            padding: collapsed ? '4px' : '12px',
            display: collapsed ? 'flex' : undefined,
            alignItems: collapsed ? 'center' : undefined,
            justifyContent: collapsed ? 'center' : undefined,
          }}
          title={collapsed ? `Engine · ${exp?.id ?? 'no run'}` : undefined}
        >
          {collapsed ? (
            <span className="relative flex h-2 w-2">
              <span
                className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-50"
                style={{ background: authError ? 'var(--as-error)' : 'var(--as-verify)' }}
              />
              <span
                className="relative inline-flex h-2 w-2 rounded-full"
                style={{ background: authError ? 'var(--as-error)' : 'var(--as-verify)' }}
              />
            </span>
          ) : (
            <>
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="relative flex h-1.5 w-1.5 shrink-0">
                    <span
                      className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-50"
                      style={{ background: authError ? 'var(--as-error)' : 'var(--as-verify)' }}
                    />
                    <span
                      className="relative inline-flex h-1.5 w-1.5 rounded-full"
                      style={{ background: authError ? 'var(--as-error)' : 'var(--as-verify)' }}
                    />
                  </span>
                  <span className="text-[12px] leading-tight whitespace-nowrap" style={{ color: 'var(--as-text-2)' }}>
                    {authError ? 'auth error' : 'engine online'}
                  </span>
                </div>
                <span className="mono text-[10.5px] whitespace-nowrap" style={{ color: 'var(--as-text-3)' }}>
                  {agentCount || STAGE_META.length} agts
                </span>
              </div>

              <div className="mt-2.5 border-t pt-2" style={{ borderColor: 'var(--as-border)' }}>
                <div className="flex items-center justify-between gap-2">
                  <span className="mono truncate text-[11px]" style={{ color: 'var(--as-text-2)' }}>
                    {exp?.id ? `${exp.id.slice(0, 8)}…` : '—'}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${tone.dot}`} />
                    <span className="mono text-[10px] uppercase" style={{ color: 'var(--as-text-3)' }}>
                      {tone.label}
                    </span>
                  </span>
                </div>
                <div className="mt-1.5 flex items-center justify-between gap-2">
                  <span className="truncate text-[11px]" style={{ color: 'var(--as-text-3)' }} title={exp?.dataset}>
                    {exp?.dataset ?? 'no dataset'}
                  </span>
                  <span className="mono text-[11px] whitespace-nowrap" style={{ color: 'var(--as-text-2)' }}>
                    {isLive ? elapsedLabel : exp?.runtime ?? '—'}
                  </span>
                </div>
                {/* Progress bar */}
                <div className="mt-2 h-[3px] w-full overflow-hidden rounded-full" style={{ background: 'var(--as-border)' }}>
                  <div
                    className="h-full rounded-full transition-all duration-500 ease-out"
                    style={{
                      width: `${progress}%`,
                      background: exp?.status === 'FAILED'
                        ? 'var(--as-error)'
                        : exp?.status === 'COMPLETED'
                          ? 'var(--as-verify)'
                          : 'linear-gradient(90deg, var(--as-accent), var(--as-teal))',
                    }}
                  />
                </div>
                <div className="mono mt-1 flex justify-between text-[10px]" style={{ color: 'var(--as-text-3)' }}>
                  <span>stage {doneStages}/{totalStages}</span>
                  <span>{progress}%</span>
                </div>
              </div>

              {/* User section */}
              <div
                className="mono mt-2 flex items-center justify-between border-t pt-1.5 text-[11px]"
                style={{ borderColor: 'var(--as-border)', color: 'var(--as-text-3)' }}
              >
                <div className="relative">
                  <button
                    onClick={() => setUserMenuOpen(!userMenuOpen)}
                    className="flex items-center gap-1.5 truncate pr-4 transition-colors hover:!text-[var(--as-text)]"
                    aria-label="User menu"
                    aria-expanded={userMenuOpen}
                  >
                    <User className="w-3.5 h-3.5 flex-shrink-0" />
                    <span className="truncate" title={userEmail}>{userEmail}</span>
                    <ChevronDown
                      className={`w-3 h-3 flex-shrink-0 transition-transform ${userMenuOpen ? 'rotate-180' : ''}`}
                    />
                  </button>
                  {userMenuOpen && (
                    <div className="absolute bottom-full left-0 right-0 mb-1 z-20 anim-slide-up">
                      <div
                        className="rounded-2xl border py-1.5 shadow-xl"
                        style={{
                          background: 'var(--as-glass-bg-2)',
                          borderColor: 'var(--as-border)',
                          backdropFilter: 'blur(20px)',
                          WebkitBackdropFilter: 'blur(20px)',
                        }}
                      >
                        <div className="px-3 py-1.5 border-b mb-1" style={{ borderColor: 'var(--as-border)' }}>
                          <p className="text-[11px] font-semibold truncate" style={{ color: 'var(--as-text)' }}>
                            {user?.name ?? 'Guest User'}
                          </p>
                          <p className="text-[10px] truncate" style={{ color: 'var(--as-text-3)' }}>
                            {user?.email ?? 'guest@autosage.local'}
                          </p>
                        </div>
                        <button
                          onClick={() => { setUserMenuOpen(false); logout() }}
                          className="w-full flex items-center gap-2 px-3 py-1.5 text-[12px] rounded-lg mx-1 transition-colors hover:bg-[var(--as-glass-bg)]"
                          style={{ color: 'var(--as-text-2)', width: 'calc(100% - 8px)' }}
                        >
                          <LogOut className="w-3.5 h-3.5" />
                          Sign out
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </aside>
  )
}

export function PageHeader({
  title,
  subtitle,
  right,
}: {
  title: string
  subtitle?: string
  right?: React.ReactNode
}) {
  return (
    <header
      className="flex items-end justify-between gap-6 border-b px-8 py-7"
      style={{ borderColor: 'var(--as-border)' }}
    >
      <div>
        <h1 className="text-[20px] font-semibold tracking-tight" style={{ color: 'var(--as-text)' }}>{title}</h1>
        {subtitle && (
          <p className="mt-1.5 max-w-[74ch] text-[15px] leading-relaxed" style={{ color: 'var(--as-text-2)' }}>
            {subtitle}
          </p>
        )}
      </div>
      {right}
    </header>
  )
}
