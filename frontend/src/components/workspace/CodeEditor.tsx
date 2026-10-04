import { useEffect, useRef, useCallback } from 'react'
import { EditorView, basicSetup } from 'codemirror'
import { placeholder as placeholderExtension } from '@codemirror/view'
import { EditorState, Compartment } from '@codemirror/state'
import { python } from '@codemirror/lang-python'
import { javascript } from '@codemirror/lang-javascript'
import { json } from '@codemirror/lang-json'
import { yaml } from '@codemirror/lang-yaml'
import { oneDark } from '@codemirror/theme-one-dark'
import { keymap } from '@codemirror/view'
import { indentWithTab } from '@codemirror/commands'
import { lineNumbers, highlightActiveLineGutter } from '@codemirror/view'

interface CodeEditorProps {
  value: string
  onChange: (value: string) => void
  language?: 'python' | 'javascript' | 'json' | 'yaml' | 'plaintext'
  readOnly?: boolean
  placeholder?: string
  className?: string
}

export function CodeEditor({
  value,
  onChange,
  language = 'python',
  readOnly = false,
  placeholder = '',
  className = '',
}: CodeEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const viewRef = useRef<EditorView | null>(null)
  const currentValueRef = useRef(value)

  const languageSupport = useCallback(() => {
    switch (language) {
      case 'python':
        return python()
      case 'javascript':
        return javascript()
      case 'json':
        return json()
      case 'yaml':
        return yaml()
      default:
        return []
    }
  }, [language])

  const languageCompartment = useRef(new Compartment())
  const readOnlyCompartment = useRef(new Compartment())

  useEffect(() => {
    if (!containerRef.current || viewRef.current) return

    const initialState = EditorState.create({
      doc: value,
      extensions: [
        basicSetup,
        keymap.of([indentWithTab]),
        lineNumbers(),
        highlightActiveLineGutter(),
        oneDark,
        languageSupport(),
        readOnly ? EditorState.readOnly.of(true) : [],
        EditorView.updateListener.of((update: { docChanged: boolean; state: { doc: { toString: () => string } } }) => {
          if (update.docChanged) {
            currentValueRef.current = update.state.doc.toString()
            onChange(currentValueRef.current)
          }
        }),
        placeholderExtension(placeholder),
      ],
    })

    const view = new EditorView({
      state: initialState,
      parent: containerRef.current,
    })

    viewRef.current = view

    return () => {
      view.destroy()
      viewRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!viewRef.current) return
    if (currentValueRef.current !== value) {
      viewRef.current.dispatch({
        changes: {
          from: 0,
          to: viewRef.current.state.doc.length,
          insert: value,
        },
      })
      currentValueRef.current = value
    }
  }, [value])

  useEffect(() => {
    if (!viewRef.current) return
    viewRef.current.dispatch({
      effects: languageCompartment.current.reconfigure(languageSupport()),
    })
  }, [language, languageSupport])

  useEffect(() => {
    if (!viewRef.current) return
    viewRef.current.dispatch({
      effects: readOnlyCompartment.current.reconfigure(
        readOnly ? EditorState.readOnly.of(true) : []
      ),
    })
  }, [readOnly])

  return (
    <div
      ref={containerRef}
      className={`cm-editor flex-1 ${className}`}
      style={{
        height: '100%',
        fontFamily: 'var(--font-mono)',
        fontSize: '13px',
        lineHeight: '1.6',
      }}
    />
  )
}