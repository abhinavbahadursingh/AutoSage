import { useEffect, useState, useRef, useMemo, useCallback } from 'react'
import {
  RotateCcw,
  CheckCircle,
  AlertCircle,
  Loader2,
  Dock,
  X,
  Copy,
  TerminalSquare,
  FileCode,
  Zap,
  Trash2,
  ChevronDown,
  Maximize2,
  Minimize2,
  Download,
  GripVertical,
  GripHorizontal,
} from 'lucide-react'
import { api } from '../../lib/api'

interface SandboxStatus {
  available: boolean
  error: string | null
  config?: {
    image_tag: string
    cpu_limit: number
    memory_limit: string
    timeout_sec: number
    workspace_size: string
    pids_limit: number
    readonly_rootfs: boolean
  }
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

interface LogEntry {
  type: 'stdout' | 'stderr' | 'system' | 'result'
  content: string
  timestamp: Date
}

const TEMPLATES = {
  'Random Forest': `import os
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
model = RandomForestClassifier(n_estimators=200, max_depth=10, random_state=42, n_jobs=-1)
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

  'XGBoost': `import os
import json
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
import joblib

# Load dataset
df = pd.read_csv('/workspace/dataset.csv')
X = df.drop('target', axis=1)
y = df['target']

# Split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

# Train
model = XGBClassifier(
    n_estimators=200,
    max_depth=6,
    learning_rate=0.1,
    subsample=0.8,
    colsample_bytree=0.8,
    random_state=42,
    n_jobs=-1,
    eval_metric='logloss'
)
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

with open('/workspace/metrics.json', 'w') as f:
    json.dump(metrics, f)

joblib.dump(model, '/workspace/model.joblib')

print("Training completed successfully")
print(f"Accuracy: {metrics['accuracy']:.4f}")
print(f"F1: {metrics['f1']:.4f}")
print(f"ROC-AUC: {metrics['roc_auc']:.4f}")`,

  'LightGBM': `import os
import json
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from lightgbm import LGBMClassifier
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
import joblib

# Load dataset
df = pd.read_csv('/workspace/dataset.csv')
X = df.drop('target', axis=1)
y = df['target']

# Split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

# Train
model = LGBMClassifier(
    n_estimators=200,
    max_depth=7,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    random_state=42,
    n_jobs=-1,
    verbosity=-1
)
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

with open('/workspace/metrics.json', 'w') as f:
    json.dump(metrics, f)

joblib.dump(model, '/workspace/model.joblib')

print("Training completed successfully")
print(f"Accuracy: {metrics['accuracy']:.4f}")
print(f"F1: {metrics['f1']:.4f}")
print(f"ROC-AUC: {metrics['roc_auc']:.4f}")`,

  'Neural Net (PyTorch)': `import os
import json
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
import joblib

# Load dataset
df = pd.read_csv('/workspace/dataset.csv')
X = df.drop('target', axis=1).values.astype(np.float32)
y = df['target'].values.astype(np.float32)

# Split & scale
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
scaler = StandardScaler()
X_train = scaler.fit_transform(X_train)
X_test = scaler.transform(X_test)

# Convert to tensors
X_train_t = torch.FloatTensor(X_train)
y_train_t = torch.FloatTensor(y_train).unsqueeze(1)
X_test_t = torch.FloatTensor(X_test)
y_test_t = torch.FloatTensor(y_test).unsqueeze(1)

# Model
class Net(nn.Module):
    def __init__(self, input_dim):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )
    def forward(self, x):
        return self.net(x)

model = Net(X_train.shape[1])
criterion = nn.BCELoss()
optimizer = optim.Adam(model.parameters(), lr=0.001)

# Train
model.train()
for epoch in range(50):
    optimizer.zero_grad()
    output = model(X_train_t)
    loss = criterion(output, y_train_t)
    loss.backward()
    optimizer.step()

# Evaluate
model.eval()
with torch.no_grad():
    y_proba = model(X_test_t).numpy().flatten()
    y_pred = (y_proba > 0.5).astype(int)

metrics = {
    "accuracy": float(accuracy_score(y_test, y_pred)),
    "f1": float(f1_score(y_test, y_pred)),
    "roc_auc": float(roc_auc_score(y_test, y_proba)),
}

with open('/workspace/metrics.json', 'w') as f:
    json.dump(metrics, f)

torch.save(model.state_dict(), '/workspace/model.pt')
joblib.dump(scaler, '/workspace/scaler.joblib')

print("Training completed successfully")
print(f"Accuracy: {metrics['accuracy']:.4f}")
print(f"F1: {metrics['f1']:.4f}")
print(f"ROC-AUC: {metrics['roc_auc']:.4f}")`,

  'Blank': `import os
import json
import pandas as pd
import numpy as np

# Your training script here
# Dataset will be available at: /workspace/dataset.csv
# Write metrics to: /workspace/metrics.json
# Save artifacts to: /workspace/

print("Hello from the sandbox!")`,
}

function highlightPython(code: string): string {
  return code
    .replace(/("""[\s\S]*?"""|'''[\s\S]*?'''|"[^"\\]*(?:\\.[^"\\]*)*"|'[^'\\]*(?:\\.[^'\\]*)*')/g, '<span class="token-string">$1</span>')
    .replace(/(#.*$)/gm, '<span class="token-comment">$1</span>')
    .replace(/\b(\d+\.?\d*)\b/g, '<span class="token-number">$1</span>')
    .replace(/\b(import|from|as|def|class|return|if|elif|else|for|while|try|except|finally|with|raise|assert|lambda|yield|global|nonlocal|pass|break|continue|and|or|not|in|is|True|False|None|async|await)\b/g, '<span class="token-keyword">$1</span>')
    .replace(/\b(print|len|range|enumerate|zip|map|filter|sorted|list|dict|set|tuple|str|int|float|bool|open)\b/g, '<span class="token-builtin">$1</span>')
    .replace(/\b([A-Z][a-zA-Z0-9_]*)\b/g, '<span class="token-class">$1</span>')
    .replace(/\b([a-z_][a-zA-Z0-9_]*)\s*(?=\()/g, '<span class="token-function">$1</span>')
}

interface PanelSizes {
  editor: number
  terminal: number
  results: number
}

const DEFAULT_SIZES: PanelSizes = { editor: 35, terminal: 45, results: 20 }
const MIN_PANEL_SIZE = 15

export function Sandbox() {
  const [status, setStatus] = useState<SandboxStatus>({ available: false, error: 'not probed' })
  const [isRunning, setIsRunning] = useState(false)
  const [result, setResult] = useState<ExecutionResult | null>(null)
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [script, setScript] = useState<string>(TEMPLATES['Random Forest'])
  const [activeTemplate, setActiveTemplate] = useState<'Random Forest' | 'XGBoost' | 'LightGBM' | 'Neural Net (PyTorch)' | 'Blank'>('Random Forest')
  const [showTemplatePicker, setShowTemplatePicker] = useState(false)
  const [layout, setLayout] = useState<'split' | 'editor' | 'terminal'>('split')
  const [sizes, setSizes] = useState<PanelSizes>(DEFAULT_SIZES)
  const [dragging, setDragging] = useState<'editor-terminal' | 'terminal-results' | null>(null)
  const terminalRef = useRef<HTMLDivElement>(null)
  const editorRef = useRef<HTMLTextAreaElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    fetchStatus()
  }, [])

  const fetchStatus = async () => {
    try {
      const status = await api.sandboxStatus()
      setStatus(status)
    } catch (err) {
      setStatus({ available: false, error: err instanceof Error ? err.message : 'Failed to fetch status' })
    }
  }

  const addLog = (type: LogEntry['type'], content: string) => {
    setLogs(prev => [...prev, { type, content, timestamp: new Date() }])
  }

  const clearLogs = () => setLogs([])

  const copyScript = async () => {
    await navigator.clipboard.writeText(script)
    addLog('system', 'Script copied to clipboard')
  }

  const downloadScript = () => {
    const blob = new Blob([script], { type: 'text/python' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'train_script.py'
    a.click()
    URL.revokeObjectURL(url)
  }

  const runScript = async () => {
    setIsRunning(true)
    clearLogs()
    addLog('system', `Starting sandbox execution…`)
    addLog('system', `Job ID: sandbox-${Date.now().toString(36)}`)
    setResult(null)

    try {
      const data = await api.sandboxExecute({ script, dataset_path: null, env_vars: {} })
      setResult(data)

      if (data.stdout) {
        data.stdout.split('\n').filter(Boolean).forEach(line => addLog('stdout', line))
      }
      if (data.stderr) {
        data.stderr.split('\n').filter(Boolean).forEach(line => addLog('stderr', line))
      }

      addLog('result', `Execution completed in ${data.duration_sec.toFixed(2)}s`)
      addLog('result', `Exit code: ${data.exit_code}`)
      if (data.success) {
        addLog('result', `✓ Metrics: ${Object.entries(data.metrics).map(([k, v]) => `${k}=${v.toFixed(4)}`).join(', ')}`)
        if (data.artifacts.length) {
          addLog('result', `✓ Artifacts: ${data.artifacts.join(', ')}`)
        }
      } else {
        addLog('result', `✗ Error: ${data.error_message}`)
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      addLog('stderr', `Error: ${msg}`)
      addLog('result', `Execution failed: ${msg}`)
      setResult({
        success: false,
        job_id: '',
        metrics: {},
        artifacts: [],
        stdout: '',
        stderr: msg,
        error_type: 'NetworkError',
        error_message: msg,
        duration_sec: 0,
        exit_code: null,
      })
    } finally {
      setIsRunning(false)
    }
  }

  const scrollToBottom = () => {
    requestAnimationFrame(() => {
      terminalRef.current?.scrollTo({ top: terminalRef.current.scrollHeight, behavior: 'smooth' })
    })
  }

  useEffect(() => { scrollToBottom() }, [logs])

  const highlightedScript = useMemo(() => highlightPython(script), [script])

  const handleDragStart = useCallback((e: React.MouseEvent, type: 'editor-terminal' | 'terminal-results') => {
    e.preventDefault()
    e.stopPropagation()
    setDragging(type)
    document.body.style.cursor = type === 'editor-terminal' ? 'col-resize' : 'row-resize'
    document.body.style.userSelect = 'none'
  }, [])

  const handleDragMove = useCallback((e: MouseEvent) => {
    if (!dragging || !containerRef.current) return
    const container = containerRef.current.getBoundingClientRect()
    const totalWidth = container.width
    const totalHeight = container.height

    if (dragging === 'editor-terminal') {
      const editorWidth = e.clientX - container.left
      const editorPercent = Math.max(MIN_PANEL_SIZE, Math.min(100 - MIN_PANEL_SIZE * 2, (editorWidth / totalWidth) * 100))
      const remaining = 100 - editorPercent
      const terminalPercent = Math.max(MIN_PANEL_SIZE, remaining - MIN_PANEL_SIZE)
      const resultsPercent = remaining - terminalPercent
      setSizes({ editor: editorPercent, terminal: terminalPercent, results: resultsPercent })
    } else if (dragging === 'terminal-results' && result) {
      const terminalBottom = container.bottom - e.clientY
      const resultsPercent = Math.max(MIN_PANEL_SIZE, Math.min(100 - sizes.editor - MIN_PANEL_SIZE, (terminalBottom / totalHeight) * 100))
      const terminalPercent = 100 - sizes.editor - resultsPercent
      setSizes(prev => ({ ...prev, terminal: terminalPercent, results: resultsPercent }))
    }
  }, [dragging, result, sizes.editor])

  const handleDragEnd = useCallback(() => {
    setDragging(null)
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
  }, [])

  useEffect(() => {
    if (dragging) {
      document.addEventListener('mousemove', handleDragMove)
      document.addEventListener('mouseup', handleDragEnd)
      return () => {
        document.removeEventListener('mousemove', handleDragMove)
        document.removeEventListener('mouseup', handleDragEnd)
      }
    }
  }, [dragging, handleDragMove, handleDragEnd])

  const editorWidth = layout === 'split' ? sizes.editor : 100
  const terminalWidth = layout === 'split' ? sizes.terminal : layout === 'terminal' ? 100 : 0
  const resultsHeight = result ? sizes.results : 0

  return (
    <div
      ref={containerRef}
      className="sandbox-root flex h-full flex-col rounded-2xl border border-ink-600 bg-ink-900/90 overflow-hidden shadow-[0_0_40px_-10px_rgba(168,85,247,0.15)]"
    >
      {/* Header Bar */}
      <header className="flex items-center justify-between gap-4 border-b border-ink-600/50 px-4 py-3 bg-ink-950/50 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 p-1.5 rounded-lg bg-ink-800/50 border border-ink-600/50">
            <Dock className="h-5 w-5 text-accent-400" />
          </div>
          <div>
            <h2 className="text-[14px] font-semibold text-paper-50 tracking-tight">Docker Sandbox</h2>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span
                className={`h-1.5 w-1.5 rounded-full transition-colors ${
                  status.available ? 'bg-verify-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'bg-conflict-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]'
                }`}
              />
              <span className="mono text-[11px] font-medium text-paper-400 uppercase tracking-wider">
                {status.available ? 'Ready' : 'Unavailable'}
              </span>
              {status.config && (
                <>
                  <span className="text-paper-600">·</span>
                  <span className="mono text-[10px] text-paper-500">{status.config.image_tag}</span>
                  <span className="text-paper-600">·</span>
                  <span className="mono text-[10px] text-paper-500">{status.config.cpu_limit} CPU · {status.config.memory_limit}</span>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={fetchStatus}
            disabled={isRunning}
            className="p-2 rounded-lg text-paper-400 transition-all hover:bg-ink-700/50 hover:text-paper-100 disabled:opacity-40 disabled:cursor-not-allowed"
            title="Refresh sandbox status"
          >
            <RotateCcw size={16} className={isRunning ? 'animate-spin' : ''} />
          </button>

          <div className="w-px h-6 bg-ink-600/50 mx-1" />

          <div className="relative">
            <button
              onClick={() => setShowTemplatePicker(!showTemplatePicker)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium text-paper-300 transition-all hover:bg-ink-700/50 hover:text-paper-100"
            >
              <FileCode className="h-4 w-4" />
              <span>{activeTemplate}</span>
              <ChevronDown className="h-3.5 w-3.5" />
            </button>
            {showTemplatePicker && (
              <div className="absolute right-0 top-full mt-1.5 z-20 min-w-[200px] rounded-xl border border-ink-600 bg-ink-900 py-1.5 shadow-xl animate-fade-in">
                {Object.keys(TEMPLATES).map((name) => (
                  <button
                    key={name}
                    onClick={() => { setActiveTemplate(name as any); setScript(TEMPLATES[name as keyof typeof TEMPLATES]); setShowTemplatePicker(false); }}
                    className={`w-full flex items-center gap-3 px-3 py-2 text-[13px] transition-colors ${activeTemplate === name ? 'bg-accent-500/10 text-accent-300' : 'text-paper-300 hover:bg-ink-700/50 hover:text-paper-100'}`}
                  >
                    {activeTemplate === name && <CheckCircle className="h-4 w-4 text-accent-400 flex-shrink-0" />}
                    {name}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="flex items-center gap-1 bg-ink-800/50 rounded-lg p-0.5 border border-ink-600/50">
            <button
              onClick={() => setLayout('editor')}
              className={`p-2 rounded-md transition-all ${layout === 'editor' ? 'bg-ink-600/50 text-paper-100' : 'text-paper-400 hover:text-paper-200'}`}
              title="Editor only"
            >
              <FileCode className="h-4 w-4" />
            </button>
            <button
              onClick={() => setLayout('split')}
              className={`p-2 rounded-md transition-all ${layout === 'split' ? 'bg-ink-600/50 text-paper-100' : 'text-paper-400 hover:text-paper-200'}`}
              title="Split view"
            >
              <TerminalSquare className="h-4 w-4" />
            </button>
            <button
              onClick={() => setLayout('terminal')}
              className={`p-2 rounded-md transition-all ${layout === 'terminal' ? 'bg-ink-600/50 text-paper-100' : 'text-paper-400 hover:text-paper-200'}`}
              title="Terminal only"
            >
              <TerminalSquare className="h-4 w-4 rotate-90" />
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Editor Pane */}
        {(layout === 'split' || layout === 'editor') && (
          <div
            className={`flex flex-col transition-all duration-300 ease-in-out border-r border-ink-600/50 ${
              layout === 'split' ? 'flex-shrink-0' : 'w-full'
            }`}
            style={{ width: layout === 'split' ? `${editorWidth}%` : '100%' }}
          >
            <div className="flex items-center justify-between border-b border-ink-600/50 px-3 py-2 bg-ink-950/50">
              <div className="flex items-center gap-2">
                <span className="label-xs text-paper-400 uppercase tracking-wider">Editor</span>
                <span className="mono text-[10px] text-paper-500 px-2 py-0.5 rounded bg-ink-700/50">Python</span>
              </div>
              <div className="flex items-center gap-1">
                <button onClick={copyScript} className="p-1.5 rounded text-paper-400 hover:bg-ink-700/50 hover:text-paper-100 transition-colors" title="Copy script">
                  <Copy className="h-3.5 w-3.5" />
                </button>
                <button onClick={downloadScript} className="p-1.5 rounded text-paper-400 hover:bg-ink-700/50 hover:text-paper-100 transition-colors" title="Download script">
                  <Download className="h-3.5 w-3.5" />
                </button>
                <button onClick={() => { setScript(''); addLog('system', 'Editor cleared') }} className="p-1.5 rounded text-paper-400 hover:bg-ink-700/50 hover:text-paper-100 transition-colors" title="Clear editor">
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>

            <div className="flex-1 overflow-auto relative min-h-0">
                <textarea
                  ref={editorRef}
                  value={script}
                  onChange={(e) => setScript(e.target.value)}
                  onScroll={(e) => {
                    const highlightOverlay = e.currentTarget.nextElementSibling as HTMLElement
                    if (highlightOverlay) {
                      highlightOverlay.scrollTop = e.currentTarget.scrollTop
                      highlightOverlay.scrollLeft = e.currentTarget.scrollLeft
                    }
                  }}
                  disabled={isRunning}
                  spellCheck={false}
                  className="editor-textarea w-full min-h-full bg-transparent border-none resize-none p-4 text-[13px] leading-relaxed font-mono text-paper-100 placeholder-paper-600 focus:outline-none selection:bg-accent-500/30"
                  placeholder="# Write your training script here..."
                  style={{
                    fontFamily: '"JetBrains Mono", "Fira Code", "Monaco", monospace',
                    fontSize: '13px',
                    lineHeight: '1.6',
                    tabSize: 4,
                  }}
                />
                <div className="pointer-events-none absolute inset-0 p-4 text-[13px] leading-relaxed font-mono whitespace-pre" style={{
                  fontFamily: '"JetBrains Mono", "Fira Code", "Monaco", monospace',
                  fontSize: '13px',
                  lineHeight: '1.6',
                  color: 'transparent',
                  whiteSpace: 'pre-wrap',
                  wordWrap: 'break-word',
                }}>
                  {highlightedScript.split('\n').map((line, i) => (
                    <div key={i} className="relative h-5" dangerouslySetInnerHTML={{ __html: line || ' ' }} />
                  ))}
                </div>
            </div>

            <div className="border-t border-ink-600/50 px-3 py-2 bg-ink-950/50 flex items-center justify-between text-[11px] text-paper-500">
              <span>{script.split('\n').length} lines · {script.length} chars</span>
              <span className="mono">UTF-8 · LF · Python</span>
            </div>
          </div>
        )}

        {/* Vertical Resizer: Editor ↔ Terminal */}
        {layout === 'split' && (
          <div
            className="resizer-v w-1 cursor-col-resize flex items-center justify-center transition-colors hover:bg-accent-500/20 active:bg-accent-500/30"
            style={{ background: 'linear-gradient(180deg, transparent 40%, var(--as-border) 50%, transparent 60%)' }}
            onMouseDown={(e) => handleDragStart(e, 'editor-terminal')}
            title="Drag to resize editor"
          >
            <GripVertical className="h-8 w-3 text-ink-500/50" />
          </div>
        )}

        {/* Terminal + Results Container */}
        <div className="flex-1 flex flex-col relative min-w-0 overflow-hidden">
          {/* Terminal Pane */}
          {(layout === 'split' || layout === 'terminal') && (
            <div
              className={`flex flex-col transition-all duration-300 ease-in-out flex-shrink-0 ${
                layout === 'split' ? '' : 'w-full'
              }`}
              style={{ 
                width: layout === 'split' ? `${terminalWidth}%` : '100%',
                height: layout === 'split' ? `calc(100% - ${resultsHeight}%)` : '100%'
              }}
            >
              <div className="flex items-center justify-between border-b border-ink-600/50 px-3 py-2 bg-ink-950/50">
                <div className="flex items-center gap-2">
                  <span className="label-xs text-paper-400 uppercase tracking-wider">Terminal</span>
                  <span className={`mono text-[10px] font-medium px-2 py-0.5 rounded ${
                    isRunning ? 'bg-accent-500/20 text-accent-300 animate-pulse' :
                    result?.success ? 'bg-verify-500/20 text-verify-400' :
                    result?.success === false ? 'bg-conflict-500/20 text-conflict-400' :
                    'bg-ink-700/50 text-paper-500'
                  }`}>
                    {isRunning ? 'Running' : result?.success ? 'Success' : result?.success === false ? 'Failed' : 'Idle'}
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <button onClick={clearLogs} className="p-1.5 rounded text-paper-400 hover:bg-ink-700/50 hover:text-paper-100 transition-colors" title="Clear terminal">
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                  <button onClick={() => setLayout(layout === 'split' ? 'terminal' : 'split')} className="p-1.5 rounded text-paper-400 hover:bg-ink-700/50 hover:text-paper-100 transition-colors" title="Toggle layout">
                    {layout === 'split' ? <Maximize2 className="h-3.5 w-3.5" /> : <Minimize2 className="h-3.5 w-3.5" />}
                  </button>
                </div>
              </div>

              <div
                ref={terminalRef}
                className="terminal-output flex-1 overflow-y-auto p-4 font-mono text-[12.5px] leading-relaxed"
                style={{
                  fontFamily: '"JetBrains Mono", "Fira Code", "Monaco", monospace',
                  fontSize: '12.5px',
                  lineHeight: '1.6',
                  color: 'var(--as-text-2)',
                }}
              >
                {logs.length === 0 ? (
                  <div className="terminal-welcome flex h-full flex-col items-center justify-center gap-4 text-paper-500/60">
                    <div className="flex flex-col items-center gap-2 opacity-60">
                      <TerminalSquare className="h-12 w-12 text-ink-500" />
                      <p className="text-[14px] font-medium text-paper-400">Terminal Ready</p>
                      <p className="text-[12px] text-center max-w-[280px]">Select a template or write your script, then press <kbd className="px-2 py-0.5 rounded bg-ink-700 border border-ink-500 text-paper-200 font-mono text-[11px]">Run in Sandbox</kbd> to execute in the isolated Docker environment.</p>
                    </div>
                    <div className="grid grid-cols-2 gap-2 max-w-[280px] text-[11px] text-paper-500">
                      <div className="p-2 rounded-lg bg-ink-800/50 border border-ink-600/50"><kbd className="font-mono text-paper-300">Ctrl+Enter</kbd> Run script</div>
                      <div className="p-2 rounded-lg bg-ink-800/50 border border-ink-600/50"><kbd className="font-mono text-paper-300">Ctrl+L</kbd> Clear terminal</div>
                      <div className="p-2 rounded-lg bg-ink-800/50 border border-ink-600/50"><kbd className="font-mono text-paper-300">Alt+E</kbd> Focus editor</div>
                      <div className="p-2 rounded-lg bg-ink-800/50 border border-ink-600/50"><kbd className="font-mono text-paper-300">Alt+T</kbd> Focus terminal</div>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col gap-1">
                    {logs.map((entry, i) => (
                      <div
                        key={i}
                        className={`terminal-line flex items-start gap-2 animate-slide-up ${
                          entry.type === 'stderr' ? 'text-conflict-400' :
                          entry.type === 'system' ? 'text-accent-300/80' :
                          entry.type === 'result' ? 'text-verify-400' :
                          'text-paper-300'
                        }`}
                        style={{ opacity: entry.type === 'system' ? 0.7 : 1 }}
                      >
                        <span className="terminal-timestamp shrink-0 text-[11px] text-paper-500 font-mono tabular-nums" style={{ width: '64px' }}>
                          {entry.timestamp.toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                        </span>
                        <span className={`flex-1 break-all whitespace-pre-wrap ${entry.type === 'system' ? 'italic' : ''}`}>
                          {entry.content}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Run Bar */}
              <div className="terminal-runbar border-t border-ink-600/50 px-4 py-3 bg-ink-950/50 flex items-center justify-between gap-4">
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  {result && (
                    <div className="flex items-center gap-3 flex-wrap text-[11px]">
                      <span className="flex items-center gap-1.5 text-paper-400">
                        <span>Duration:</span>
                        <span className="mono text-accent-300 font-medium">{result.duration_sec.toFixed(2)}s</span>
                      </span>
                      <span className="flex items-center gap-1.5 text-paper-400">
                        <span>Exit:</span>
                        <span className={`mono font-medium ${result.exit_code === 0 ? 'text-verify-400' : 'text-conflict-400'}`}>
                          {result.exit_code ?? 'N/A'}
                        </span>
                      </span>
                      {Object.keys(result.metrics).length > 0 && (
                        <span className="flex items-center gap-1.5 text-paper-400">
                          <span>Metrics:</span>
                          <span className="mono text-paper-200">
                            {Object.entries(result.metrics).map(([k, v]) => `${k}=${v.toFixed(4)}`).join(', ')}
                          </span>
                        </span>
                      )}
                    </div>
                  )}
                </div>

                <button
                  onClick={runScript}
                  disabled={isRunning || !status.available}
                  className="run-button flex items-center gap-2 h-10 px-5 rounded-xl font-semibold text-[13px] transition-all disabled:cursor-not-allowed disabled:opacity-40
                    bg-accent-500 text-white
                    hover:!bg-accent-400 hover:shadow-[0_0_20px_var(--as-accent-glow)] active:scale-[0.98]
                    focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-400/50 focus-visible:ring-offset-2 focus-visible:ring-offset-ink-950"
                  style={{ boxShadow: '0 4px 16px var(--as-accent-glow)' }}
                >
                  {isRunning ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>Running…</span>
                    </>
                  ) : (
                    <>
                      <Zap className="h-4 w-4" />
                      <span>Run in Sandbox</span>
                      <kbd className="hidden sm:inline-flex px-1.5 py-0.5 rounded text-[10px] font-mono bg-white/10 border border-white/5">Ctrl+Enter</kbd>
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {/* Horizontal Resizer: Terminal ↔ Results */}
          {result && layout === 'split' && (
            <div
              className="resizer-h h-1 cursor-row-resize w-full flex items-center justify-center transition-colors hover:bg-accent-500/20 active:bg-accent-500/30"
              style={{ background: 'linear-gradient(90deg, transparent 40%, var(--as-border) 50%, transparent 60%)' }}
              onMouseDown={(e) => handleDragStart(e, 'terminal-results')}
              title="Drag to resize results panel"
            >
              <GripHorizontal className="h-3 w-8 text-ink-500/50" />
            </div>
          )}

          {/* Results Panel */}
          {result && (
            <div
              className="results-panel flex-shrink-0 border-t border-ink-600/50 bg-ink-950/95 backdrop-blur-sm p-4 animate-slide-up"
              style={{ height: layout === 'split' ? `${resultsHeight}%` : 'auto', minHeight: '120px', maxHeight: layout === 'split' ? `${resultsHeight}%` : '40vh' }}
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-[12px] font-semibold uppercase tracking-wider text-paper-400">Execution Result</h3>
                <button
                  onClick={() => setResult(null)}
                  className="p-1.5 rounded text-paper-400 hover:text-paper-100 hover:bg-ink-700/50 transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 mb-4">
                <ResultCard label="Status" value={result.success ? 'Success' : 'Failed'} tone={result.success ? 'verify' : 'conflict'} icon={result.success ? CheckCircle : AlertCircle} />
                <ResultCard label="Duration" value={`${result.duration_sec.toFixed(2)}s`} icon={Loader2} />
                <ResultCard label="Exit Code" value={String(result.exit_code ?? 'N/A')} tone={result.exit_code === 0 ? 'verify' : 'conflict'} icon={TerminalSquare} />
                <ResultCard label="Artifacts" value={String(result.artifacts.length)} icon={FileCode} />
              </div>

              {Object.keys(result.metrics).length > 0 && (
                <div className="mb-4">
                  <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-paper-400">Metrics</h4>
                  <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                    {Object.entries(result.metrics).map(([key, value]) => (
                      <div key={key} className="rounded-lg border border-ink-600/50 bg-ink-800/50 px-3 py-2.5 transition-all hover:border-ink-500 hover:bg-ink-800">
                        <div className="mono text-[10px] text-paper-500 uppercase tracking-wider">{key}</div>
                        <div className="mono tnum mt-0.5 text-[19px] font-medium text-paper-100">{Number(value).toFixed(4)}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {result.artifacts.length > 0 && (
                <div className="mb-4">
                  <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-paper-400">Artifacts</h4>
                  <div className="flex flex-wrap gap-2">
                    {result.artifacts.map((artifact) => (
                      <span key={artifact} className="flex items-center gap-1.5 rounded-lg bg-ink-800/50 border border-ink-600/50 px-3 py-1.5 text-[12px] font-mono text-paper-300 hover:border-ink-500 hover:bg-ink-800 transition-all">
                        <FileCode className="h-3.5 w-3.5 text-paper-400" />
                        {artifact}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {(result.error_type || result.error_message) && (
                <div className="rounded-xl border border-conflict-500/30 bg-conflict-500/10 p-4">
                  <div className="flex items-center gap-2 text-conflict-400">
                    <AlertCircle className="h-5 w-5 flex-shrink-0" />
                    <span className="font-medium text-[13px]">Error: {result.error_type || 'Unknown'}</span>
                  </div>
                  <p className="mt-2 text-[13px] text-paper-300 leading-relaxed">{result.error_message}</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function ResultCard({ label, value, tone, icon: Icon }: { label: string; value: string; tone?: 'verify' | 'conflict'; icon: React.ComponentType<{ size?: number; className?: string }> }) {
  return (
    <div className="rounded-xl border border-ink-600/50 bg-ink-800/50 p-3 transition-all hover:border-ink-500 hover:bg-ink-800">
      <div className="flex items-center gap-1.5 mb-1.5">
        <Icon className="h-3.5 w-3.5 text-paper-400" />
        <span className="text-[10px] font-semibold uppercase tracking-wider text-paper-400">{label}</span>
      </div>
      <div className={`mono tnum text-[20px] font-semibold ${tone === 'verify' ? 'text-verify-400' : tone === 'conflict' ? 'text-conflict-400' : 'text-paper-100'}`}>
        {value}
      </div>
    </div>
  )
}