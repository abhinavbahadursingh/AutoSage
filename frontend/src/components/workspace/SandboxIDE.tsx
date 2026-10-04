import { useState, useCallback, useEffect, useRef } from 'react'
import { Play, RotateCcw, AlertCircle, Loader2, Dock, Terminal, LayoutPanelLeft, Maximize2, Copy } from 'lucide-react'
import { api } from '../../lib/api'
import { CodeEditor } from './CodeEditor'
import { FileTabs } from './FileTabs'
import { FileExplorer, generateMockFileTree } from './FileExplorer'
import { Terminal as TerminalComponent } from './Terminal'
import { StatusBar } from './StatusBar'

interface SandboxStatus {
  available: boolean
  error: string | null
}

interface ExecutionResult {
  success: boolean
  job_id: string
  metrics: Record<string, number>
  artifacts: string[]
  stdout: string
  stderr: string
  error_type: string | null
  error_message: string | null
  duration_sec: number
  exit_code: number | null
}

interface FileTab {
  id: string
  name: string
  path: string
  language: 'python' | 'javascript' | 'json' | 'yaml' | 'plaintext'
  content: string
  modified: boolean
  active: boolean
}

const DEFAULT_FILES: FileTab[] = [
  {
    id: 'main',
    name: 'train.py',
    path: '/workspace/train.py',
    language: 'python',
    content: `import os
import json
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
import joblib

# Load dataset
df = pd.read_csv('/workspace/dataset.csv')
X = df.drop('target', axis=1)
y = df['target']

# Split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

# Train
model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42, n_jobs=-1)
model.fit(X_train, y_train)

# Predict
y_pred = model.predict(X_test)
y_proba = model.predict_proba(X_test)[:, 1]

# Metrics
metrics = {
    "accuracy": float(accuracy_score(y_test, y_pred)),
    "f1": float(f1_score(y_test, y_pred)),
    "roc_auc": float(roc_auc_score(y_test, y_proba)),
}

# Save metrics
with open('/workspace/metrics.json', 'w') as f:
    json.dump(metrics, f)

# Save model
joblib.dump(model, '/workspace/model.joblib')

print("Training completed successfully")
print(f"Accuracy: {metrics['accuracy']:.4f}")
print(f"F1: {metrics['f1']:.4f}")
print(f"ROC-AUC: {metrics['roc_auc']:.4f}")`,
    modified: false,
    active: true,
  },
  {
    id: 'config',
    name: 'config.yaml',
    path: '/workspace/config.yaml',
    language: 'yaml',
    content: `# Training Configuration
model:
  type: RandomForestClassifier
  params:
    n_estimators: 100
    max_depth: 5
    random_state: 42
    n_jobs: -1

data:
  path: /workspace/dataset.csv
  target_column: target
  test_size: 0.2
  stratify: true

output:
  metrics_path: /workspace/metrics.json
  model_path: /workspace/model.joblib

logging:
  level: INFO
  format: json`,
    modified: false,
    active: false,
  },
  {
    id: 'dataset_info',
    name: 'dataset.csv',
    path: '/workspace/dataset.csv',
    language: 'plaintext',
    content: `# Dataset Info
# This is a placeholder for the dataset file
# The actual CSV data will be mounted at runtime
# Columns: feature_1, feature_2, ..., target`,
    modified: false,
    active: false,
  },
]

type TerminalLineType = 'output' | 'error' | 'system' | 'command' | 'prompt'

interface TerminalLine {
  id: number
  type: TerminalLineType
  content: string
  timestamp?: Date
}

const INITIAL_TERMINAL_LINES: TerminalLine[] = [
  { id: 1, type: 'system', content: 'AutoSage Docker Sandbox v2.0', timestamp: new Date() },
  { id: 2, type: 'system', content: 'Environment: Python 3.11 + ML Stack (scikit-learn, XGBoost, LightGBM, PyTorch)', timestamp: new Date() },
  { id: 3, type: 'system', content: 'Workspace: /workspace (persistent)', timestamp: new Date() },
  { id: 4, type: 'system', content: 'Type "help" for available commands', timestamp: new Date() },
]

export function SandboxIDE() {
  const [status, setStatus] = useState<SandboxStatus>({ available: false, error: 'not probed' })
  const [isRunning, setIsRunning] = useState(false)
  const [result, setResult] = useState<ExecutionResult | null>(null)
  const [terminalLines, setTerminalLines] = useState<TerminalLine[]>(INITIAL_TERMINAL_LINES)
  const [fileTabs, setFileTabs] = useState<FileTab[]>(DEFAULT_FILES)
  const [activeTabId, setActiveTabId] = useState<string>('main')
  const [explorerVisible, setExplorerVisible] = useState(true)
  const [terminalVisible, setTerminalVisible] = useState(true)
  const [terminalHeight, setTerminalHeight] = useState(300)
  const lineIdCounter = useRef(5)

  useEffect(() => {
    fetchStatus()
  }, [])

  const fetchStatus = useCallback(async () => {
    try {
      const status = await api.sandboxStatus()
      setStatus({ available: status.available, error: status.error })
    } catch (err) {
      setStatus({ available: false, error: err instanceof Error ? err.message : 'Failed to fetch status' })
    }
  }, [])

  const getActiveTab = useCallback(() => {
    return fileTabs.find((tab) => tab.id === activeTabId) || fileTabs[0]
  }, [fileTabs, activeTabId])

  const updateTabContent = useCallback((tabId: string, content: string) => {
    setFileTabs((prev) =>
      prev.map((tab) =>
        tab.id === tabId ? { ...tab, content, modified: true } : tab
      )
    )
  }, [])

  const handleTabChange = useCallback((tabId: string) => {
    setActiveTabId(tabId)
  }, [])

  const handleTabClose = useCallback((tabId: string) => {
    setFileTabs((prev) => {
      const filtered = prev.filter((tab) => tab.id !== tabId)
      if (activeTabId === tabId && filtered.length > 0) {
        setActiveTabId(filtered[filtered.length - 1].id)
      }
      return filtered
    })
  }, [activeTabId])

  const handleTabSave = useCallback((tabId: string) => {
    setFileTabs((prev) =>
      prev.map((tab) =>
        tab.id === tabId ? { ...tab, modified: false } : tab
      )
    )
  }, [])

  const handleNewFile = useCallback(() => {
    const newTab: FileTab = {
      id: `tab-${Date.now()}`,
      name: 'untitled.py',
      path: '/workspace/untitled.py',
      language: 'python',
      content: '',
      modified: true,
      active: true,
    }
    setFileTabs((prev) => prev.map((tab) => ({ ...tab, active: false })).concat(newTab))
    setActiveTabId(newTab.id)
  }, [])

  const handleOpenFile = useCallback(() => {
    // In a real implementation, this would open a file picker
    console.log('Open file dialog')
  }, [])

  const addTerminalLine = useCallback((line: { type: TerminalLineType; content: string; timestamp?: Date }) => {
    const newLine = {
      ...line,
      id: lineIdCounter.current++,
      timestamp: line.timestamp || new Date(),
    }
    setTerminalLines((prev) => [...prev, newLine])
  }, [])

  const clearTerminal = useCallback(() => {
    setTerminalLines(INITIAL_TERMINAL_LINES)
    lineIdCounter.current = 5
  }, [])

  const handleTerminalCommand = useCallback((command: string) => {
    addTerminalLine({ type: 'command', content: command, timestamp: new Date() })

    // Handle built-in commands
    if (command === 'help') {
      addTerminalLine({ type: 'system', content: 'Available commands:', timestamp: new Date() })
      addTerminalLine({ type: 'output', content: '  help       - Show this help', timestamp: new Date() })
      addTerminalLine({ type: 'output', content: '  clear      - Clear terminal', timestamp: new Date() })
      addTerminalLine({ type: 'output', content: '  ls         - List files', timestamp: new Date() })
      addTerminalLine({ type: 'output', content: '  pwd        - Print working directory', timestamp: new Date() })
      addTerminalLine({ type: 'output', content: '  python     - Run Python interpreter', timestamp: new Date() })
      addTerminalLine({ type: 'output', content: '  python <file> - Run Python script', timestamp: new Date() })
      return
    }

    if (command === 'clear') {
      clearTerminal()
      return
    }

    if (command === 'ls') {
      addTerminalLine({ type: 'output', content: 'dataset.csv  train.py  config.yaml  metrics.json  model.joblib', timestamp: new Date() })
      addTerminalLine({ type: 'output', content: 'src/  notebooks/', timestamp: new Date() })
      return
    }

    if (command === 'pwd') {
      addTerminalLine({ type: 'output', content: '/workspace', timestamp: new Date() })
      return
    }

    if (command.startsWith('python ')) {
      const script = command.slice(7)
      addTerminalLine({ type: 'system', content: `Running Python script: ${script}`, timestamp: new Date() })
      addTerminalLine({ type: 'output', content: 'Python 3.11.5 (main, Aug 24 2023) on linux', timestamp: new Date() })
      addTerminalLine({ type: 'output', content: 'Type "help", "copyright", "credits" or "license" for more information.', timestamp: new Date() })
      return
    }

    if (command === 'python') {
      addTerminalLine({ type: 'system', content: 'Starting Python REPL...', timestamp: new Date() })
      addTerminalLine({ type: 'output', content: 'Python 3.11.5 (main, Aug 24 2023) on linux', timestamp: new Date() })
      addTerminalLine({ type: 'output', content: '>>> ', timestamp: new Date() })
      return
    }

    addTerminalLine({ type: 'error', content: `Command not found: ${command}`, timestamp: new Date() })
    addTerminalLine({ type: 'output', content: 'Type "help" for available commands', timestamp: new Date() })
  }, [addTerminalLine, clearTerminal])

  const runScript = useCallback(async () => {
    const activeTab = getActiveTab()
    if (!activeTab) return

    setIsRunning(true)
    setResult(null)
    addTerminalLine({ type: 'system', content: 'Starting sandbox execution...', timestamp: new Date() })
    addTerminalLine({ type: 'command', content: `python ${activeTab.name}`, timestamp: new Date() })

    try {
      const data = await api.sandboxExecute({
        script: activeTab.content,
        dataset_path: null,
        env_vars: {},
      })

      setResult(data)

      if (data.stdout) {
        data.stdout.split('\n').filter(Boolean).forEach((line) => {
          addTerminalLine({ type: 'output', content: line, timestamp: new Date() })
        })
      }

      if (data.stderr) {
        addTerminalLine({ type: 'error', content: 'STDERR:', timestamp: new Date() })
        data.stderr.split('\n').filter(Boolean).forEach((line) => {
          addTerminalLine({ type: 'error', content: line, timestamp: new Date() })
        })
      }

      addTerminalLine({ type: 'system', content: 'Sandbox execution completed.', timestamp: new Date() })
      addTerminalLine({ type: 'output', content: `Exit code: ${data.exit_code}`, timestamp: new Date() })
      addTerminalLine({ type: 'output', content: `Duration: ${data.duration_sec.toFixed(2)}s`, timestamp: new Date() })

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : String(err)
      addTerminalLine({ type: 'error', content: 'Error executing sandbox job:', timestamp: new Date() })
      addTerminalLine({ type: 'error', content: errorMessage, timestamp: new Date() })

      setResult({
        success: false,
        job_id: '',
        metrics: {},
        artifacts: [],
        stdout: '',
        stderr: errorMessage,
        error_type: 'NetworkError',
        error_message: errorMessage,
        duration_sec: 0,
        exit_code: null,
      })
    } finally {
      setIsRunning(false)
    }
  }, [getActiveTab, addTerminalLine])

  const handleExplorerToggle = useCallback(() => {
    setExplorerVisible((prev) => !prev)
  }, [])

  const handleTerminalToggle = useCallback(() => {
    setTerminalVisible((prev) => !prev)
  }, [])

  const handleTerminalResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault()

    const handleMouseMove = (moveEvent: MouseEvent) => {
      const container = document.querySelector('.sandbox-ide-container')
      if (!container) return
      const containerRect = container.getBoundingClientRect()
      const newHeight = containerRect.bottom - moveEvent.clientY
      setTerminalHeight(Math.max(150, Math.min(600, newHeight)))
    }

    const handleMouseUp = () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
  }, [])

  const activeTab = getActiveTab()

  return (
    <div className="sandbox-ide-container flex h-full flex-col rounded-2xl border border-ink-600 bg-ink-900/80 overflow-hidden">
      {/* Main Toolbar */}
      <header className="flex items-center justify-between gap-4 border-b border-ink-600 px-3 py-2 bg-ink-800/50">
        <div className="flex items-center gap-3">
          <Dock className="h-5 w-5 text-accent-400" />
          <div>
            <h2 className="text-[14px] font-semibold text-paper-50">Docker Sandbox IDE</h2>
            <div className="flex items-center gap-2 mt-0.5">
              <span
                className={`h-2 w-2 rounded-full ${status.available ? 'bg-verify-500' : 'bg-conflict-500'}`}
              />
              <span className="mono text-[11px] text-paper-400">
                {status.available ? 'Sandbox Available' : 'Sandbox Unavailable'}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={handleExplorerToggle}
            className={`p-2 rounded-lg transition-colors ${
              explorerVisible
                ? 'text-accent-400 bg-accent-900/30'
                : 'text-paper-400 hover:text-paper-100 hover:bg-ink-700'
            }`}
            title={explorerVisible ? 'Hide Explorer (Ctrl+B)' : 'Show Explorer (Ctrl+B)'}
            aria-label={explorerVisible ? 'Hide Explorer' : 'Show Explorer'}
          >
            <LayoutPanelLeft className="h-4 w-4" />
          </button>
          <button
            onClick={handleTerminalToggle}
            className={`p-2 rounded-lg transition-colors ${
              terminalVisible
                ? 'text-teal-400 bg-teal-900/30'
                : 'text-paper-400 hover:text-paper-100 hover:bg-ink-700'
            }`}
            title={terminalVisible ? 'Hide Terminal (Ctrl+J)' : 'Show Terminal (Ctrl+J)'}
            aria-label={terminalVisible ? 'Hide Terminal' : 'Show Terminal'}
          >
            <Terminal className="h-4 w-4" />
          </button>
          <button
            onClick={fetchStatus}
            disabled={isRunning}
            className="p-2 rounded-lg text-paper-400 transition-colors hover:text-paper-100 hover:bg-ink-700 disabled:opacity-50"
            title="Refresh Status"
            aria-label="Refresh Status"
          >
            <RotateCcw className="h-4 w-4" />
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Explorer Sidebar */}
        {explorerVisible && (
          <div className="w-64 flex flex-col border-r border-ink-600 transition-all duration-200">
            <FileExplorer
              rootNodes={generateMockFileTree()}
              onFileSelect={(file) => {
                if (file.type === 'file') {
                  const existingTab = fileTabs.find((tab) => tab.path === file.path)
                  if (existingTab) {
                    setActiveTabId(existingTab.id)
                  } else {
                    const newTab: FileTab = {
                      id: `tab-${file.id}`,
                      name: file.name,
                      path: file.path,
                      language: file.language || 'plaintext',
                      content: `# ${file.name}\n# Opened from explorer`,
                      modified: false,
                      active: true,
                    }
                    setFileTabs((prev) => prev.map((tab) => ({ ...tab, active: false })).concat(newTab))
                    setActiveTabId(newTab.id)
                  }
                }
              }}
              onNewFile={handleNewFile}
              onNewFolder={handleNewFile}
              onDelete={() => {}}
              onRename={() => {}}
            />
          </div>
        )}

        {/* Editor Area */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* File Tabs */}
          <FileTabs
            tabs={fileTabs}
            activeTabId={activeTabId}
            onTabChange={handleTabChange}
            onTabClose={handleTabClose}
            onTabSave={handleTabSave}
            onNewFile={handleNewFile}
            onOpenFile={handleOpenFile}
          />

          {/* Editor */}
          <div className="flex-1 flex flex-col min-w-0 relative">
            {activeTab && (
              <CodeEditor
                value={activeTab.content}
                onChange={(content) => updateTabContent(activeTab.id, content)}
                language={activeTab.language}
                readOnly={isRunning}
                placeholder={`# ${activeTab.name} - Edit your code here...`}
              />
            )}
          </div>
        </div>

        {/* Terminal Panel */}
        {terminalVisible && (
          <div className="flex flex-col min-w-0 border-l border-ink-600 transition-all duration-200" style={{ width: terminalVisible ? '400px' : '0' }}>
            <div
              className="h-1 bg-ink-600 hover:bg-accent-400 cursor-row-resize transition-colors"
              onMouseDown={handleTerminalResize}
              style={{ cursor: 'row-resize' }}
              aria-label="Resize terminal"
            />
            <TerminalComponent
              lines={terminalLines}
              onClear={clearTerminal}
              onSendCommand={handleTerminalCommand}
              isRunning={isRunning}
              height={terminalHeight}
            />
          </div>
        )}
      </div>

      {/* Results Panel */}
      {result && (
        <div className="border-t border-ink-600 bg-ink-850/50 p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-[13px] font-semibold uppercase tracking-wide text-paper-400">Execution Result</h3>
            <div className="flex items-center gap-2">
              <button className="p-1.5 rounded text-paper-400 hover:text-paper-100 hover:bg-ink-700 transition-colors" title="Copy Results" aria-label="Copy Results">
                <Copy className="h-3.5 w-3.5" />
              </button>
              <button className="p-1.5 rounded text-paper-400 hover:text-paper-100 hover:bg-ink-700 transition-colors" title="Expand" aria-label="Expand">
                <Maximize2 className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard
              label="Success"
              value={result.success ? 'Yes' : 'No'}
              tone={result.success ? 'verify' : 'conflict'}
            />
            <MetricCard
              label="Duration"
              value={`${result.duration_sec.toFixed(2)}s`}
            />
            <MetricCard
              label="Exit Code"
              value={String(result.exit_code ?? 'N/A')}
              tone={result.exit_code === 0 ? 'verify' : 'conflict'}
            />
            <MetricCard
              label="Artifacts"
              value={String(result.artifacts.length)}
            />
          </div>

          {Object.keys(result.metrics).length > 0 && (
            <div className="mt-4">
              <h4 className="mb-2 text-[12px] font-semibold uppercase tracking-wide text-paper-400">Metrics</h4>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {Object.entries(result.metrics).map(([key, value]) => (
                  <div key={key} className="rounded-lg border border-ink-600 bg-ink-800 px-3 py-2">
                    <div className="mono text-[11px] text-paper-500 uppercase">{key}</div>
                    <div className="mono tnum text-[18px] text-paper-100">{Number(value).toFixed(4)}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {result.artifacts.length > 0 && (
            <div className="mt-4">
              <h4 className="mb-2 text-[12px] font-semibold uppercase tracking-wide text-paper-400">Artifacts</h4>
              <ul className="flex flex-wrap gap-2">
                {result.artifacts.map((artifact) => (
                  <li key={artifact} className="rounded bg-ink-700 px-2.5 py-1 text-[12px] font-mono text-paper-300">
                    {artifact}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {(result.error_type || result.error_message) && (
            <div className="mt-4 rounded-lg border border-conflict-500/30 bg-conflict-500/10 p-3">
              <div className="flex items-center gap-2 text-conflict-400">
                <AlertCircle size={14} />
                <span className="font-medium">Error: {result.error_type || 'Unknown'}</span>
              </div>
              <p className="mt-1 text-[13px] text-paper-300">{result.error_message}</p>
            </div>
          )}
        </div>
      )}

      {/* Status Bar */}
      <StatusBar
        language={activeTab?.language === 'python' ? 'Python' : activeTab?.language === 'json' ? 'JSON' : activeTab?.language === 'yaml' ? 'YAML' : 'Plain Text'}
        cursorPosition={{ line: 1, column: 1 }}
        indentSize={4}
        indentType="spaces"
        cpuUsage={isRunning ? Math.floor(Math.random() * 30) + 40 : 0}
        memoryUsage={isRunning ? Math.floor(Math.random() * 20) + 30 : 0}
        diskUsage={15}
        networkStatus="connected"
        gitBranch="main"
        gitChanges={fileTabs.filter((t) => t.modified).length}
      />

      {/* Run Button Bar */}
      <div className="flex items-center justify-between gap-3 border-t border-ink-600 bg-ink-800/50 px-4 py-3">
        <div className="flex items-center gap-3">
          {result && (
            <div className="flex items-center gap-2 text-[12px]">
              <span className="text-paper-400">Duration:</span>
              <span className="mono text-accent-300">{result.duration_sec.toFixed(2)}s</span>
              <span className="text-paper-400">Exit:</span>
              <span className={`mono ${result.exit_code === 0 ? 'text-verify-400' : 'text-conflict-400'}`}>
                {result.exit_code ?? 'N/A'}
              </span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={runScript}
            disabled={isRunning || !status.available || !activeTab}
            className="flex h-[36px] items-center gap-2 rounded-xl px-5 text-[13.5px] font-medium transition-all disabled:cursor-not-allowed disabled:opacity-50"
            style={{
              background: 'var(--as-accent)',
              borderColor: 'var(--as-accent)',
              color: '#fff',
            }}
          >
            {isRunning ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Running...
              </>
            ) : (
              <>
                <Play size={14} />
                Run in Sandbox
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

function MetricCard({ label, value, tone }: { label: string; value: string; tone?: 'verify' | 'conflict' }) {
  return (
    <div className="rounded-lg border border-ink-600 bg-ink-800 px-3 py-2.5">
      <div className="text-[11px] tracking-[0.08em] font-semibold uppercase text-paper-500">{label}</div>
      <div className={`mono tnum mt-1 text-[18px] font-semibold ${tone === 'verify' ? 'text-verify-400' : tone === 'conflict' ? 'text-conflict-400' : 'text-paper-100'}`}>
        {value}
      </div>
    </div>
  )
}