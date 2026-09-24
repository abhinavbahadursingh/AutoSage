import {
  Boxes,
  Database,
  FlaskConical,
  LayoutGrid,
  Library,
  PanelLeftClose,
  PanelLeftOpen,
  ScrollText,
  Settings2,
  ShieldCheck,
} from 'lucide-react'
import { NavLink } from 'react-router-dom'
import type { ComponentType } from 'react'
import { useStore } from '../../store/context'
import { DATASETS, MODELS } from '../../data/catalog'
import type { ExperimentStatus } from '../../lib/types'

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
      { to: '/experiments', label: 'Experiments', icon: FlaskConical },
    ],
  },
  {
    title: 'Research',
    items: [
      { to: '/agents', label: 'Agents', icon: Boxes },
      { to: '/evidence', label: 'Evidence', icon: ShieldCheck },
      { to: '/memory', label: 'Memory', icon: Library },
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

const STATUS_TONE: Record<ExperimentStatus, { dot: string; text: string; label: string }> = {
  draft: { dot: 'bg-paper-500', text: 'text-paper-400', label: 'draft' },
  running: { dot: 'bg-accent-400', text: 'text-accent-300', label: 'running' },
  paused: { dot: 'bg-warn-500', text: 'text-warn-500', label: 'paused' },
  completed: { dot: 'bg-verify-500', text: 'text-verify-500', label: 'completed' },
  failed: { dot: 'bg-conflict-500', text: 'text-conflict-500', label: 'failed' },
}

export function Logo({ compact = false, hideName = false }: { compact?: boolean; hideName?: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <svg width="17" height="17" viewBox="0 0 32 32" aria-hidden className="shrink-0">
        <rect width="32" height="32" rx="5" fill="#121418" stroke="#232830" />
        <path d="M8 22 L16 8 L24 22" stroke="#ff9f43" strokeWidth="2.4" fill="none" />
        <path d="M11.5 17.5 H20.5" stroke="#ff9f43" strokeWidth="2.4" />
        <circle cx="16" cy="25" r="1.5" fill="#737c8a" />
      </svg>
      {!hideName && (
        <span
          className={`font-semibold tracking-[-0.01em] whitespace-nowrap text-paper-50 transition-all duration-200 ${
            compact ? 'text-[15.5px]' : 'text-[16px]'
          }`}
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
        `group relative flex h-[32px] items-center gap-2.5 rounded-sm px-2.5 text-[15.5px] transition-colors duration-150 ${
          collapsed ? 'justify-center px-0' : ''
        } ${isActive ? 'bg-ink-800 text-paper-50' : 'text-paper-400 hover:bg-ink-900 hover:text-paper-100'}`
      }
    >
      {({ isActive }) => (
        <>
          <span
            className={`absolute top-2 bottom-2 -left-2 w-[2px] rounded-r transition-all duration-200 ${
              isActive ? 'bg-accent-400 opacity-100' : 'bg-transparent opacity-0'
            }`}
          />
          <span className="relative shrink-0">
            <Icon
              size={14}
              strokeWidth={1.7}
              className={`transition-colors duration-150 ${
                isActive ? 'text-accent-400' : 'text-paper-500 group-hover:text-paper-300'
              }`}
            />
            {collapsed && count != null && count > 0 && (
              <span className="absolute -top-1 -right-1 h-[6px] w-[6px] rounded-full bg-accent-400/90 ring-1 ring-ink-950" />
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
            <span className="mono shrink-0 text-[11px] text-paper-500 transition-opacity duration-200 group-hover:text-paper-400">
              {count}
            </span>
          )}
        </>
      )}
    </NavLink>
  )
}

function GroupLabel({ title, collapsed }: { title: string; collapsed: boolean }) {
  return (
    <div
      className={`overflow-hidden px-2.5 pt-4 pb-1.5 transition-all duration-200 ${
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
  const { experiments, activeExperiment, runState, elapsedLabel, memory } = useStore()

  const agentCount = new Set(activeExperiment?.nodes.map((n) => n.agent) ?? []).size
  const counts: Record<string, number | undefined> = {
    '/experiments': experiments.length,
    '/agents': agentCount || 8,
    '/memory': memory.length,
    '/datasets': DATASETS.length,
    '/models': MODELS.length,
  }

  const exp = activeExperiment
  const tone = STATUS_TONE[exp?.status ?? 'draft']
  const totalStages = 9
  const progress = exp?.status === 'completed' ? 100 : Math.round(((runState.stageIndex + 1) / totalStages) * 100)
  const isLive = exp?.status === 'running' || runState.id !== null

  return (
    <aside
      className={`group flex h-full shrink-0 flex-col overflow-hidden border-r border-ink-600 bg-ink-950/75 backdrop-blur-md transition-[width] duration-300 ease-in-out ${
        collapsed ? 'w-[56px]' : 'w-[212px]'
      }`}
    >
      <div
        className={`flex w-[212px] shrink-0 gap-2 px-3.5 pt-4 pb-4 ${
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
            className={`rounded-sm p-1.5 text-paper-500 transition-all duration-200 hover:bg-ink-800 hover:text-accent-300 focus-visible:opacity-100 ${
              collapsed ? 'opacity-0 group-hover:opacity-100' : 'ml-auto opacity-100'
            }`}
          >
            {collapsed ? <PanelLeftOpen size={14} /> : <PanelLeftClose size={14} />}
          </button>
        )}
      </div>

      <nav className="flex w-[212px] shrink-0 flex-col gap-[2px] overflow-hidden px-2 pb-2">
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
        <div className="mt-2 border-t border-ink-700/70 pt-2">
          <NavItemRow item={SETTINGS} collapsed={collapsed} onNavigate={onNavigate} />
        </div>
      </nav>

      <div className="mt-auto w-[212px] shrink-0 px-2.5 pt-3 pb-3">
        <div
          className={`rounded-sm border border-ink-600/80 bg-ink-900/60 transition-all duration-300 ${
            collapsed ? 'flex items-center justify-center border-transparent bg-transparent p-1' : 'p-2.5'
          }`}
          title={collapsed ? `Engine online · ${exp?.id ?? 'no run'}` : undefined}
        >
          {collapsed ? (
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-verify-500 opacity-50" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-verify-500" />
            </span>
          ) : (
            <>
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="relative flex h-1.5 w-1.5 shrink-0">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-verify-500 opacity-50" />
                    <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-verify-500" />
                  </span>
                  <span className="text-[12.5px] leading-tight whitespace-nowrap text-paper-300">
                    engine online
                  </span>
                </div>
                <span className="mono text-[10.5px] whitespace-nowrap text-paper-500">{agentCount || 8} agts</span>
              </div>

              <div className="mt-2.5 border-t border-ink-700/70 pt-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="mono truncate text-[11.5px] text-paper-400">{exp?.id ?? '—'}</span>
                  <span className="flex items-center gap-1.5">
                    <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${tone.dot}`} />
                    <span className={`mono text-[10.5px] uppercase ${tone.text}`}>{tone.label}</span>
                  </span>
                </div>
                <div className="mt-1.5 flex items-center justify-between gap-2">
                  <span className="truncate text-[11.5px] text-paper-500" title={exp?.dataset}>
                    {exp?.dataset ?? 'no dataset'}
                  </span>
                  <span className="mono text-[11px] whitespace-nowrap text-paper-400">
                    {isLive ? elapsedLabel : exp?.runtime ?? '—'}
                  </span>
                </div>
                <div className="mt-2 h-[3px] w-full overflow-hidden rounded-full bg-ink-700">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ease-out ${
                      exp?.status === 'failed' ? 'bg-conflict-500' : exp?.status === 'completed' ? 'bg-verify-500' : 'bg-accent-500'
                    }`}
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <div className="mono mt-1 flex justify-between text-[10px] text-paper-500">
                  <span>stage {Math.min(runState.stageIndex + 1, totalStages)}/{totalStages}</span>
                  <span>{progress}%</span>
                </div>
              </div>

              <div className="mono mt-2 flex items-center justify-between border-t border-ink-700/70 pt-1.5 text-[11px] text-paper-500">
                <span>you@lab</span>
                <span className="uppercase">{exp?.verificationLevel ?? 'strict'}</span>
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
    <header className="flex items-end justify-between gap-6 border-b border-ink-600 px-8 py-7">
      <div>
        <h1 className="text-[20.5px] font-semibold tracking-[-0.015em] text-paper-50">{title}</h1>
        {subtitle && <p className="mt-1.5 max-w-[74ch] text-[15.5px] leading-relaxed text-paper-400">{subtitle}</p>}
      </div>
      {right}
    </header>
  )
}
