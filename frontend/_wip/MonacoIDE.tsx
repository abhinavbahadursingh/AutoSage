import { useState, useCallback, useEffect, useRef } from 'react'
import MonacoEditor, { type OnMount } from '@monaco-editor/react'
import { FileCode, Plus, X, Loader2 } from 'lucide-react'

interface MonacoFile {
  id: string
  name: string
  path: string
  language: 'python' | 'yaml' | 'json' | 'plaintext'
  content: string
  modified: boolean
  active: boolean
}

interface MonacoIDEProps {
  initialFiles?: MonacoFile[]
  onSave?: (content: string, filePath: string) => void
  onLoadCode?: (code: string) => void | Promise<void>
}

const DEFAULT_FILES: MonacoFile[] = [
  {
    id: '1',
    name: 'pipeline.py',
    path: '/workspace/pipeline.py',
    language: 'python',
    content: '',
    modified: false,
    active: true,
  },
  {
    id: '2',
    name: 'config.yaml',
    path: '/workspace/config.yaml',
    language: 'yaml',
    content: '',
    modified: false,
    active: false,
  },
]

export function MonacoIDE({
  initialFiles,
  onSave,
  onLoadCode,
}: MonacoIDEProps) {
  const [files, setFiles] = useState<MonacoFile[]>(
    () => initialFiles ?? DEFAULT_FILES,
  )
  const [activeTabId, setActiveTabId] = useState<string>(
    () => (initialFiles ?? DEFAULT_FILES)[0]?.id ?? '',
  )
  const [isLoading, setIsLoading] = useState(false)
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null)

  useEffect(() => {
    if (!onLoadCode) return

    let cancelled = false
    setIsLoading(true)

    Promise.resolve(
      onLoadCode(
        '# Auto-generated pipeline code\n' +
          '# Problem: [problem statement]\n' +
          '# Task: [classification/regression]\n',
      ),
    )
      .catch((error) => {
        console.error('Failed to load code:', error)
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [onLoadCode])

  const activeFile =
    files.find((file) => file.id === activeTabId) ?? files[0]

  const handleSwitchTab = useCallback((tabId: string) => {
    setActiveTabId(tabId)
  }, [])

  const handleNewFile = useCallback(() => {
    const id = String(Date.now())
    const newFile: MonacoFile = {
      id,
      name: 'untitled.py',
      path: `/workspace/untitled_${id}.py`,
      language: 'python',
      content: '',
      modified: false,
      active: true,
    }

    setFiles((previous) => [...previous, newFile])
    setActiveTabId(id)
  }, [])

  const handleCloseTab = useCallback(
    (tabId: string) => {
      setFiles((previous) => {
        const filtered = previous.filter((file) => file.id !== tabId)

        if (activeTabId === tabId) {
          setActiveTabId(filtered.at(-1)?.id ?? '')
        }

        return filtered
      })
    },
    [activeTabId],
  )

  const handleEditorMount: OnMount = useCallback((editor) => {
    editorRef.current = editor
  }, [])

  const handleEditorChange = useCallback(
    (value: string | undefined) => {
      if (!activeFile) return

      const content = value ?? ''

      setFiles((previous) =>
        previous.map((file) =>
          file.id === activeFile.id
            ? { ...file, content, modified: true }
            : file,
        ),
      )

      onSave?.(content, activeFile.path)
    },
    [activeFile, onSave],
  )

  return (
    <div className="workspace-container min-h-screen bg-black text-white">
      <header className="border-b border-[color-mix(in_oklch,var(--as-border)_50%,black)] bg-[color-mix(in_oklch,var(--as-accent)_5%,black)]">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <FileCode className="h-5 w-5 text-[color-mix(in_oklch,var(--as-accent)_40%,white)]" />
            <h1 className="text-xl font-semibold">AutoSage Monaco IDE</h1>
          </div>

          <button
            type="button"
            onClick={handleNewFile}
            className="rounded-lg p-2 transition-colors hover:bg-[color-mix(in_oklch,var(--as-accent)_10%,black)]"
            title="New file"
            aria-label="Create new file"
          >
            <Plus className="h-4 w-4 text-[color-mix(in_oklch,var(--as-accent)_50%,white)]" />
          </button>
        </div>
      </header>

      <div className="flex min-h-[600px]">
        <aside className="flex w-64 flex-col border-r border-[color-mix(in_oklch,var(--as-border)_30%,black)]">
          <div className="flex items-center justify-between border-b border-[color-mix(in_oklch,var(--as-border)_30%,black)] px-3 py-2">
            <span className="text-[11px] font-medium uppercase tracking-wider text-white/60">
              Files
            </span>
            <button
              type="button"
              onClick={handleNewFile}
              className="flex items-center gap-1 rounded-md bg-[color-mix(in_oklch,var(--as-accent)_10%,black)] px-2 py-1 text-[10px] text-[color-mix(in_oklch,var(--as-accent)_60%,white)] transition-colors hover:bg-[color-mix(in_oklch,var(--as-accent)_15%,black)]"
              title="New file"
            >
              <Plus className="h-3 w-3" />
              New
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-2">
            <div className="space-y-1">
              {files.map((file) => {
                const isActive = activeTabId === file.id

                return (
                  <button
                    key={file.id}
                    type="button"
                    onClick={() => handleSwitchTab(file.id)}
                    className={`flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-[11px] font-medium transition-all ${
                      isActive
                        ? 'border-b-2 border-[color-mix(in_oklch,var(--as-accent)_50%,black)] bg-[color-mix(in_oklch,var(--as-accent)_15%,black)] text-[color-mix(in_oklch,var(--as-accent)_80%,white)]'
                        : 'text-white/50 hover:bg-[color-mix(in_oklch,var(--as-accent)_5%,black)]'
                    }`}
                  >
                    <span
                      className={`h-2 w-2 shrink-0 rounded-full ${
                        isActive
                          ? 'bg-[color-mix(in_oklch,var(--as-accent)_60%,white)]'
                          : 'bg-transparent'
                      }`}
                    />
                    <span className="min-w-0 flex-1 truncate">{file.name}</span>
                    {file.modified && (
                      <span className="ml-1 text-xs text-[color-mix(in_oklch,var(--as-accent)_50%,white)]">
                        •
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          </div>
        </aside>

        <main className="flex min-w-0 flex-1 flex-col">
          <div className="overflow-x-auto border-b border-[color-mix(in_oklch,var(--as-border)_30%,black)] py-1">
            <div className="mx-auto flex max-w-[1200px] gap-1 px-2">
              {files.map((file) => {
                const isActive = activeTabId === file.id

                return (
                  <div
                    key={file.id}
                    className={`flex items-center gap-2 rounded-md px-3 py-1.5 text-[10px] font-medium transition-all ${
                      isActive
                        ? 'border-b-2 border-[color-mix(in_oklch,var(--as-accent)_50%,black)] bg-[color-mix(in_oklch,var(--as-accent)_15%,black)] text-[color-mix(in_oklch,var(--as-accent)_80%,white)]'
                        : 'text-white/50 hover:bg-[color-mix(in_oklch,var(--as-accent)_8%,black)] hover:text-[color-mix(in_oklch,var(--as-accent)_50%,white)]'
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => handleSwitchTab(file.id)}
                      className="flex min-w-0 items-center gap-2"
                      title={file.name}
                    >
                      <span
                        className={`h-2 w-2 shrink-0 rounded-full ${
                          isActive
                            ? 'bg-[color-mix(in_oklch,var(--as-accent)_50%,white)]'
                            : 'bg-transparent'
                        }`}
                      />
                      <span className="max-w-40 truncate">{file.name}</span>
                      {file.modified && (
                        <span className="text-xs text-[color-mix(in_oklch,var(--as-accent)_50%,white)]">
                          •
                        </span>
                      )}
                    </button>

                    <button
                      type="button"
                      onClick={() => handleCloseTab(file.id)}
                      className="ml-1 rounded p-1 text-white/50 hover:bg-white/10 hover:text-white"
                      title={`Close ${file.name}`}
                      aria-label={`Close ${file.name}`}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                )
              })}

              {files.length === 0 && (
                <span className="px-2 py-1 text-[10px] text-white/40">
                  No files
                </span>
              )}
            </div>
          </div>

          <div className="relative min-h-[500px] flex-1">
            {isLoading ? (
              <div className="flex h-[500px] items-center justify-center gap-2 text-sm text-white/70">
                <Loader2 className="h-5 w-5 animate-spin" />
                Loading...
              </div>
            ) : activeFile ? (
              <MonacoEditor
                path={activeFile.path}
                value={activeFile.content}
                language={activeFile.language}
                theme="vs-dark"
                width="100%"
                height="100%"
                onMount={handleEditorMount}
                onChange={handleEditorChange}
                options={{
                  fontFamily: '"SF Mono", "Roboto Mono", "Ubuntu Mono", monospace',
                  fontSize: 13,
                  automaticLayout: true,
                  scrollBeyondLastLine: false,
                  quickSuggestions: {
                    other: true,
                    comments: true,
                    strings: true,
                  },
                  parameterHints: { enabled: true },
                  autoClosingBrackets: 'languageDefined',
                  autoClosingQuotes: 'languageDefined',
                  smoothScrolling: true,
                  minimap: { enabled: false },
                  contextmenu: true,
                  rulers: [],
                  tabSize: 4,
                  wordWrap: 'on',
                }}
              />
            ) : (
              <div className="flex h-[500px] flex-col items-center justify-center gap-3 text-sm text-white/50">
                <FileCode className="h-8 w-8" />
                No file open. Create a new file to start editing.
                <button
                  type="button"
                  onClick={handleNewFile}
                  className="rounded-md bg-white/10 px-3 py-2 text-white hover:bg-white/15"
                >
                  Create file
                </button>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  )
}
