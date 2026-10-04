import { useRef, useEffect, useState, useCallback } from 'react'
import { X, Copy, Trash2, Maximize2, Terminal as TerminalIcon, Send } from 'lucide-react'

interface TerminalLine {
  id: number
  type: 'output' | 'error' | 'system' | 'command' | 'prompt'
  content: string
  timestamp?: Date
}

interface TerminalProps {
  lines: TerminalLine[]
  onClear: () => void
  onSendCommand?: (command: string) => void
  isRunning?: boolean
  className?: string
  height?: number
}

const DEFAULT_PROMPT = 'root@autosage:/workspace# '

export function Terminal({
  lines,
  onClear,
  onSendCommand,
  isRunning = false,
  className = '',
  height = 300,
}: TerminalProps) {
  const terminalRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const [commandHistory, setCommandHistory] = useState<string[]>([])
  const [historyIndex, setHistoryIndex] = useState(-1)
  const [copiedLine, setCopiedLine] = useState<number | null>(null)

  const scrollToBottom = useCallback(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight
    }
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [lines, scrollToBottom])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!onSendCommand) return

    const input = inputRef.current
    if (!input) return

    if (e.key === 'Enter') {
      const command = input.value.trim()
      if (command) {
        onSendCommand(command)
        setCommandHistory((prev) => [command, ...prev.slice(0, 49)])
        setHistoryIndex(-1)
        input.value = ''
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      if (historyIndex < commandHistory.length - 1) {
        setHistoryIndex((prev) => prev + 1)
        input.value = commandHistory[historyIndex + 1]
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      if (historyIndex > 0) {
        setHistoryIndex((prev) => prev - 1)
        input.value = commandHistory[historyIndex - 1]
      } else if (historyIndex === 0) {
        setHistoryIndex(-1)
        input.value = ''
      }
    }
  }

  const handleCopyLine = (line: TerminalLine) => {
    navigator.clipboard.writeText(line.content)
    setCopiedLine(line.id)
    setTimeout(() => setCopiedLine(null), 2000)
  }

  const getLineClassName = (line: TerminalLine) => {
    switch (line.type) {
      case 'error':
        return 'text-conflict-400'
      case 'system':
        return 'text-accent-400'
      case 'command':
        return 'text-teal-400'
      case 'prompt':
        return 'text-verify-400'
      default:
        return 'text-paper-300'
    }
  }

  const getLinePrefix = (line: TerminalLine) => {
    switch (line.type) {
      case 'command':
        return `${DEFAULT_PROMPT}`
      case 'prompt':
        return `${DEFAULT_PROMPT}`
      case 'system':
        return '[SYSTEM] '
      case 'error':
        return '[ERROR] '
      default:
        return ''
    }
  }

  return (
    <div className={`flex flex-col h-full bg-ink-900 rounded-xl border border-ink-600 overflow-hidden ${className}`} style={{ height }}>
      <div className="flex items-center justify-between h-8 px-3 border-b border-ink-600 bg-ink-800">
        <div className="flex items-center gap-2">
          <TerminalIcon className="h-4 w-4 text-accent-400" />
          <span className="label-xs text-paper-400">TERMINAL</span>
          {isRunning && (
            <span className="flex items-center gap-1 text-[11px] text-accent-400">
              <span className="h-1.5 w-1.5 rounded-full bg-accent-400 animate-pulse" />
              Running
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={onClear}
            className="p-1.5 rounded text-paper-400 hover:text-paper-100 hover:bg-ink-700 transition-colors"
            title="Clear Terminal"
            aria-label="Clear Terminal"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
          <button
            className="p-1.5 rounded text-paper-400 hover:text-paper-100 hover:bg-ink-700 transition-colors"
            title="Maximize"
            aria-label="Maximize"
          >
            <Maximize2 className="h-3.5 w-3.5" />
          </button>
          <button
            className="p-1.5 rounded text-paper-400 hover:text-paper-100 hover:bg-ink-700 transition-colors"
            title="Close"
            aria-label="Close"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <div
        ref={terminalRef}
        className="flex-1 overflow-y-auto p-3 font-mono text-[12.5px] leading-relaxed"
        style={{ color: 'var(--as-text-2)' }}
        role="log"
        aria-live="polite"
      >
        {lines.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-paper-500 gap-2">
            <TerminalIcon className="h-8 w-8 opacity-50" />
            <p className="text-[13px]">Terminal ready</p>
            <p className="text-[11px]">Click the input below to start typing commands</p>
          </div>
        ) : (
          <div className="flex flex-col gap-0.5">
            {lines.map((line) => (
              <div
                key={line.id}
                className={`flex gap-2 break-all ${getLineClassName(line)} anim-log-in`}
                onContextMenu={(e) => {
                  e.preventDefault()
                  handleCopyLine(line)
                }}
              >
                <span className="flex-shrink-0 text-paper-500 select-none">
                  {getLinePrefix(line)}
                </span>
                <span className="break-all select-text">{line.content}</span>
                {copiedLine === line.id && (
                  <Copy className="h-3 w-3 text-verify-400 ml-2 flex-shrink-0" />
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {onSendCommand && (
        <div className="flex items-center gap-2 border-t border-ink-600 px-3 py-2 bg-ink-800">
          <span className="text-paper-400 text-[12px] font-mono select-none">{DEFAULT_PROMPT}</span>
          <input
            ref={inputRef}
            type="text"
            onKeyDown={handleKeyDown}
            className="flex-1 bg-transparent border-none text-paper-100 placeholder-paper-500 text-[12.5px] font-mono focus:outline-none"
            placeholder="Type a command..."
            autoFocus
            disabled={isRunning}
            aria-label="Terminal command input"
          />
          <button
            onClick={() => {
              if (inputRef.current?.value.trim() && onSendCommand) {
                onSendCommand(inputRef.current.value.trim())
                setCommandHistory((prev) => [inputRef.current!.value.trim(), ...prev.slice(0, 49)])
                setHistoryIndex(-1)
                inputRef.current.value = ''
              }
            }}
            disabled={isRunning || !inputRef.current?.value.trim()}
            className="p-1.5 rounded text-paper-400 hover:text-paper-100 hover:bg-ink-700 transition-colors disabled:opacity-50"
            title="Send"
            aria-label="Send command"
          >
            <Send className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
    </div>
  )
}