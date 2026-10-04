import { Cpu, MemoryStick, Database, GitBranch, Clock, Settings } from 'lucide-react'

interface StatusBarProps {
  language?: string
  encoding?: string
  lineEnding?: string
  cursorPosition?: { line: number; column: number }
  indentSize?: number
  indentType?: 'spaces' | 'tabs'
  cpuUsage?: number
  memoryUsage?: number
  diskUsage?: number
  networkStatus?: 'connected' | 'disconnected' | 'connecting'
  gitBranch?: string
  gitChanges?: number
  className?: string
}

export function StatusBar({
  language = 'Python',
  encoding = 'UTF-8',
  lineEnding = 'LF',
  cursorPosition = { line: 1, column: 1 },
  indentSize = 4,
  indentType = 'spaces',
  cpuUsage = 0,
  memoryUsage = 0,
  diskUsage = 0,
  networkStatus = 'connected',
  gitBranch = 'main',
  gitChanges = 0,
  className = '',
}: StatusBarProps) {
  const networkColors = {
    connected: 'text-verify-400',
    disconnected: 'text-conflict-400',
    connecting: 'text-warn-400',
  }

  return (
    <div className={`flex items-center justify-between h-7 px-3 bg-ink-800 border-t border-ink-600 text-[11px] ${className}`}>
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5 text-paper-400">
          <GitBranch className="h-3 w-3" />
          <span className="font-mono">{gitBranch}</span>
          {gitChanges > 0 && (
            <span className="flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] bg-accent-900/50 text-accent-300">
              {gitChanges}
            </span>
          )}
        </div>

        <div className="flex items-center gap-1.5 text-paper-400">
          <span className="font-mono">{language}</span>
        </div>

        <div className="flex items-center gap-1.5 text-paper-400">
          <span className="font-mono">{encoding}</span>
        </div>

        <div className="flex items-center gap-1.5 text-paper-400">
          <span className="font-mono">{lineEnding}</span>
        </div>

        <div className="flex items-center gap-1.5 text-paper-400">
          {indentType === 'spaces' ? (
            <>
              <span className="font-mono">Spaces: {indentSize}</span>
            </>
          ) : (
            <>
              <span className="font-mono">Tab Size: {indentSize}</span>
            </>
          )}
        </div>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5 text-paper-400">
          <span className="font-mono">
            Ln {cursorPosition.line}, Col {cursorPosition.column}
          </span>
        </div>

        <div className="flex items-center gap-1.5 text-paper-400">
          <Cpu className="h-3 w-3" />
          <span className="font-mono">{cpuUsage}%</span>
        </div>

        <div className="flex items-center gap-1.5 text-paper-400">
          <MemoryStick className="h-3 w-3" />
          <span className="font-mono">{memoryUsage}%</span>
        </div>

        <div className="flex items-center gap-1.5 text-paper-400">
          <Database className="h-3 w-3" />
          <span className="font-mono">{diskUsage}%</span>
        </div>

        <div className={`flex items-center gap-1.5 ${networkColors[networkStatus]}`}>
          <NetworkIcon className="h-3 w-3" />
        </div>

        <div className="flex items-center gap-1.5 text-paper-400">
          <Clock className="h-3 w-3" />
          <span className="font-mono">{new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
        </div>

        <button className="p-1 rounded text-paper-400 hover:text-paper-100 hover:bg-ink-700 transition-colors" title="Settings" aria-label="Settings">
          <Settings className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}

function NetworkIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12.55a11 11 0 0 1 14.08 0" />
      <path d="M1.42 9a16 16 0 0 1 21.16 0" />
      <path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
      <line x1="12" y1="20" x2="12.01" y2="20" />
    </svg>
  )
}