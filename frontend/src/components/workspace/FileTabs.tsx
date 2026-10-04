import { useState, useRef } from 'react'
import { X, FileCode, FileText, Save, MoreHorizontal } from 'lucide-react'

interface FileTab {
  id: string
  name: string
  path: string
  language: 'python' | 'javascript' | 'json' | 'yaml' | 'plaintext'
  content: string
  modified: boolean
  active: boolean
}

interface FileTabsProps {
  tabs: FileTab[]
  activeTabId: string | null
  onTabChange: (tabId: string) => void
  onTabClose: (tabId: string) => void
  onTabSave: (tabId: string) => void
  onNewFile: () => void
  onOpenFile: () => void
  maxVisibleTabs?: number
}

export function FileTabs({
  tabs,
  activeTabId,
  onTabChange,
  onTabClose,
  onTabSave,
  onNewFile,
  onOpenFile,
  maxVisibleTabs = 8,
}: FileTabsProps) {
  const [scrollOffset, setScrollOffset] = useState(0)
  const tabsRef = useRef<HTMLDivElement>(null)
  const [showDropdown, setShowDropdown] = useState(false)

  const visibleTabs = tabs.slice(scrollOffset, scrollOffset + maxVisibleTabs)
  const hiddenTabsCount = tabs.length - scrollOffset - maxVisibleTabs

  const scrollLeft = () => {
    if (scrollOffset > 0) {
      setScrollOffset((prev) => prev - 1)
    }
  }

  const scrollRight = () => {
    if (scrollOffset + maxVisibleTabs < tabs.length) {
      setScrollOffset((prev) => prev + 1)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent, tab: FileTab) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onTabChange(tab.id)
    }
  }

  return (
    <div className="flex items-center h-8 bg-ink-800 border-b border-ink-600 px-2">
      <button
        onClick={onNewFile}
        className="flex items-center gap-1.5 h-6 px-2.5 rounded-lg text-paper-400 hover:text-paper-100 hover:bg-ink-700 transition-colors text-[12px] font-medium"
        title="New File (Ctrl+N)"
        aria-label="New File"
      >
        <FileCode className="h-3.5 w-3.5" />
        <span>New</span>
      </button>

      <button
        onClick={onOpenFile}
        className="flex items-center gap-1.5 h-6 px-2.5 rounded-lg text-paper-400 hover:text-paper-100 hover:bg-ink-700 transition-colors text-[12px] font-medium ml-1"
        title="Open File (Ctrl+O)"
        aria-label="Open File"
      >
        <FileText className="h-3.5 w-3.5" />
        <span>Open</span>
      </button>

      <div className="flex-1 flex items-center ml-2 overflow-hidden relative" ref={tabsRef}>
        {scrollOffset > 0 && (
          <button
            onClick={scrollLeft}
            className="flex items-center justify-center h-full w-8 bg-gradient-to-r from-ink-800 to-transparent text-paper-400 hover:text-paper-100 transition-colors z-10"
            aria-label="Scroll tabs left"
          >
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="15 18 9 12 15 6" />
            </svg>
          </button>
        )}

        <div className="flex items-center gap-1 overflow-x-auto scrollbar-hide" role="tablist">
          {visibleTabs.map((tab) => (
            <div
              key={tab.id}
              role="tab"
              aria-selected={tab.active}
              onClick={() => onTabChange(tab.id)}
              onKeyDown={(e) => handleKeyDown(e, tab)}
              tabIndex={0}
              className={`flex items-center gap-1.5 h-6 px-3 rounded-lg transition-all min-w-0 ${
                tab.active
                  ? 'bg-ink-900 text-paper-100 border border-ink-600 shadow-sm'
                  : 'text-paper-400 hover:text-paper-100 hover:bg-ink-750'
              }`}
              title={`${tab.path}${tab.modified ? ' (modified)' : ''}`}
            >
              <span
                className={`truncate flex-1 min-w-0 ${tab.modified ? 'font-medium' : ''}`}
              >
                {tab.name}
              </span>
              {tab.modified && (
                <span className="flex-shrink-0 h-1.5 w-1.5 rounded-full bg-accent-400" aria-label="Modified" />
              )}
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  onTabClose(tab.id)
                }}
                className={`flex-shrink-0 p-0.5 rounded transition-colors ${
                  tab.active
                    ? 'text-paper-300 hover:text-conflict-400 hover:bg-conflict-500/10'
                    : 'text-paper-500 hover:text-paper-200 hover:bg-ink-700'
                }`}
                aria-label={`Close ${tab.name}`}
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          ))}

          {hiddenTabsCount > 0 && (
            <button
              onClick={() => setShowDropdown(true)}
              className="flex items-center justify-center h-6 px-2.5 rounded-lg text-paper-400 hover:text-paper-100 hover:bg-ink-700 transition-colors text-[11px]"
              aria-label={`${hiddenTabsCount} more tabs`}
            >
              <MoreHorizontal className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        {scrollOffset + maxVisibleTabs < tabs.length && !showDropdown && (
          <button
            onClick={scrollRight}
            className="flex items-center justify-center h-full w-8 bg-gradient-to-l from-ink-800 to-transparent text-paper-400 hover:text-paper-100 transition-colors z-10 ml-[-1px]"
            aria-label="Scroll tabs right"
          >
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </button>
        )}
      </div>

      <div className="flex items-center gap-1 ml-2">
        <button
          onClick={() => {
            if (activeTabId) onTabSave(activeTabId)
          }}
          disabled={!activeTabId}
          className="flex items-center gap-1 h-6 px-2.5 rounded-lg text-paper-400 hover:text-paper-100 hover:bg-ink-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          title="Save (Ctrl+S)"
          aria-label="Save"
        >
          <Save className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}