/**
 * Monaco-backed code editor for the Sandbox.
 *
 * Drop-in replacement for the former CodeMirror `CodeEditor`: identical props
 * (`value`, `onChange`, `language`, `readOnly`, `placeholder`, `className`), so
 * `SandboxIDE` — tabs, file tree, Run gating — is unchanged.
 *
 * Monaco itself is bundled rather than fetched from a CDN; see
 * `src/lib/monacoSetup.ts`.
 *
 * This editor renders a *view* of the session's code. What gets executed by
 * Run is decided in `SandboxIDE` (user-owned Python files only), never here.
 */
import { useState } from 'react'
import Editor, { type Monaco } from '@monaco-editor/react'
import type { editor } from 'monaco-editor'
import '../../lib/monacoSetup'

export type EditorLanguage = 'python' | 'javascript' | 'json' | 'yaml' | 'plaintext'

interface MonacoCodeEditorProps {
  value: string
  onChange: (value: string) => void
  language?: EditorLanguage
  readOnly?: boolean
  placeholder?: string
  className?: string
}

const FONT_STACK = '"JetBrains Mono", "Fira Code", "Monaco", monospace'

export function MonacoCodeEditor({
  value,
  onChange,
  language = 'python',
  readOnly = false,
  placeholder = '',
  className = '',
}: MonacoCodeEditorProps) {
  // Monaco has no placeholder option: an overlay is drawn over the empty
  // document instead, positioned at the real content column so it lines up
  // with where the first character would appear.
  const [contentLeft, setContentLeft] = useState(0)

  const handleMount = (instance: editor.IStandaloneCodeEditor, _monaco: Monaco) => {
    setContentLeft(instance.getLayoutInfo().contentLeft)
    instance.onDidLayoutChange((layout) => setContentLeft(layout.contentLeft))
  }

  return (
    <div className={`relative min-h-0 w-full flex-1 overflow-hidden ${className}`}>
      <Editor
        height="100%"
        width="100%"
        language={language}
        value={value}
        theme="vs-dark"
        onChange={(next) => onChange(next ?? '')}
        onMount={handleMount}
        beforeMount={(monaco) => {
          // The `theme` prop is applied by the wrapper after mount; setting it
          // here too means the very first paint is already dark instead of
          // flashing Monaco's default light theme on a cold load.
          monaco.editor.setTheme('vs-dark')
        }}
        loading={<span className="mono text-[12px] text-[var(--as-text-3)]">Loading editor…</span>}
        options={{
          readOnly,
          domReadOnly: readOnly,
          contextmenu: !readOnly,
          automaticLayout: true,
          fontFamily: FONT_STACK,
          fontSize: 13,
          lineHeight: 22,
          fontLigatures: false,
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          padding: { top: 14, bottom: 14 },
          wordWrap: 'on',
          wrappingIndent: 'indent',
          renderLineHighlight: 'line',
          renderWhitespace: 'selection',
          lineNumbersMinChars: 3,
          glyphMargin: false,
          folding: true,
          foldingHighlight: false,
          stickyScroll: { enabled: false },
          smoothScrolling: true,
          cursorBlinking: 'smooth',
          cursorSmoothCaretAnimation: 'on',
          tabSize: 4,
          insertSpaces: true,
          detectIndentation: false,
          bracketPairColorization: { enabled: true },
          guides: { indentation: true, bracketPairs: false },
          overviewRulerLanes: 0,
          scrollbar: { verticalScrollbarSize: 10, horizontalScrollbarSize: 10, useShadows: false },
          quickSuggestions: readOnly ? false : { other: true, comments: false, strings: false },
          suggestOnTriggerCharacters: !readOnly,
          parameterHints: { enabled: !readOnly },
          copyWithSyntaxHighlighting: true,
          fixedOverflowWidgets: true,
        }}
      />

      {placeholder && value === '' && (
        <div
          className="pointer-events-none absolute top-0 select-none font-mono text-[13px] text-[#6e7681]"
          style={{ left: contentLeft, paddingTop: 14, lineHeight: '22px' }}
        >
          {placeholder}
        </div>
      )}
    </div>
  )
}
