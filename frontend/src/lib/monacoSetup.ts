/**
 * Monaco setup for the app.
 *
 * `@monaco-editor/react` downloads monaco from a CDN by default. Configuring
 * it with the `monaco-editor` package that is already in `node_modules` means
 * the editor is bundled with the app instead: it works offline, and the editor
 * version always matches the type definitions we compile against.
 *
 * Monaco starts a web worker per language service (JSON, CSS, HTML, TS) and
 * falls back to the plain editor worker for everything else (Python, YAML,
 * plain text). Vite inlines them as separate chunks through the `?worker`
 * suffix, so the labels below decide which chunk serves which language.
 *
 * This module is side-effectful — import it once, before any <Editor> renders.
 */

import * as monaco from 'monaco-editor'
import { loader } from '@monaco-editor/react'

import EditorWorker from 'monaco-editor/editor/editor.worker?worker'
import JsonWorker from 'monaco-editor/language/json/json.worker?worker'
import CssWorker from 'monaco-editor/language/css/css.worker?worker'
import HtmlWorker from 'monaco-editor/language/html/html.worker?worker'
import TsWorker from 'monaco-editor/language/typescript/ts.worker?worker'

declare global {
  interface Window {
    MonacoEnvironment?: {
      getWorker: (moduleId: string, label: string) => Worker
    }
  }
}

self.MonacoEnvironment = {
  getWorker(_moduleId: string, label: string): Worker {
    switch (label) {
      case 'json':
        return new JsonWorker()
      case 'css':
      case 'scss':
      case 'less':
        return new CssWorker()
      case 'html':
      case 'handlebars':
      case 'razor':
        return new HtmlWorker()
      case 'typescript':
      case 'javascript':
        return new TsWorker()
      default:
        return new EditorWorker()
    }
  },
}

loader.config({ monaco })

export { monaco }
