import { useState, useRef, useEffect } from 'react'
import { FolderOpen, Folder, FileCode, FileText, ChevronRight, ChevronDown, MoreHorizontal, Plus, RefreshCw } from 'lucide-react'

interface FileNode {
  id: string
  name: string
  path: string
  type: 'file' | 'folder'
  language?: 'python' | 'javascript' | 'json' | 'yaml' | 'plaintext'
  children?: FileNode[]
  expanded?: boolean
}

interface FileExplorerProps {
  rootNodes: FileNode[]
  onFileSelect: (file: FileNode) => void
  onNewFile: (parentPath?: string) => void
  onNewFolder: (parentPath?: string) => void
  onDelete: (path: string) => void
  onRename: (path: string, newName: string) => void
  className?: string
}

function FileTreeNode({
  node,
  depth = 0,
  onFileSelect,
  onNewFile,
  onNewFolder,
  onDelete,
  onRename,
  selectedPath,
}: {
  node: FileNode
  depth: number
  onFileSelect: (file: FileNode) => void
  onNewFile: (parentPath?: string) => void
  onNewFolder: (parentPath?: string) => void
  onDelete: (path: string) => void
  onRename: (path: string, newName: string) => void
  selectedPath: string | null
}) {
  const [expanded, setExpanded] = useState(node.expanded ?? false)
  const [renaming, setRenaming] = useState(false)
  const [renameValue, setRenameValue] = useState(node.name)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (renaming && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [renaming])

  const handleRenameConfirm = () => {
    if (renameValue.trim() && renameValue !== node.name) {
      onRename(node.path, renameValue.trim())
    }
    setRenaming(false)
  }

  const handleRenameCancel = () => {
    setRenameValue(node.name)
    setRenaming(false)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleRenameConfirm()
    } else if (e.key === 'Escape') {
      handleRenameCancel()
    }
  }

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (node.type === 'folder') {
      setExpanded(!expanded)
    } else {
      onFileSelect(node)
    }
  }

  if (node.type === 'folder') {
    return (
      <div className="select-none">
        <div
          className={`flex items-center gap-1 h-6 px-1.5 rounded cursor-pointer transition-colors ${
            expanded ? 'bg-ink-750' : 'hover:bg-ink-750'
          }`}
          style={{ paddingLeft: `${8 + depth * 12}px` }}
          onClick={handleClick}
        >
          <button
            className="flex items-center justify-center p-0.5 text-paper-500 hover:text-paper-300 transition-colors"
            onClick={(e) => {
              e.stopPropagation()
              setExpanded(!expanded)
            }}
            aria-label={expanded ? 'Collapse folder' : 'Expand folder'}
          >
            {expanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
          </button>
          <FolderOpen className={`h-3.5 w-3.5 ${expanded ? 'text-accent-400' : 'text-paper-500'}`} />
          <span className="text-[12px] text-paper-300 truncate">{node.name}</span>
        </div>
        {expanded && node.children && (
          <div className="overflow-hidden">
            {node.children.map((child) => (
              <FileTreeNode
                key={child.id}
                node={child}
                depth={depth + 1}
                onFileSelect={onFileSelect}
                onNewFile={onNewFile}
                onNewFolder={onNewFolder}
                onDelete={onDelete}
                onRename={onRename}
                selectedPath={selectedPath}
              />
            ))}
          </div>
        )}
      </div>
    )
  }

  const isSelected = selectedPath === node.path

  return (
    <div className="select-none">
      <div
        className={`flex items-center gap-1.5 h-6 px-1.5 rounded cursor-pointer transition-all ${
          isSelected
            ? 'bg-accent-900/50 text-paper-100'
            : 'hover:bg-ink-750 text-paper-300'
        }`}
        style={{ paddingLeft: `${8 + depth * 12}px` }}
        onClick={handleClick}
        onDoubleClick={() => onFileSelect(node)}
      >
        {node.language === 'python' ? (
          <FileCode className="h-3.5 w-3.5 text-yellow-400" />
        ) : node.language === 'json' ? (
          <FileCode className="h-3.5 w-3.5 text-orange-400" />
        ) : node.language === 'yaml' ? (
          <FileCode className="h-3.5 w-3.5 text-red-400" />
        ) : (
          <FileText className="h-3.5 w-3.5 text-paper-500" />
        )}
        {renaming ? (
          <input
            ref={inputRef}
            type="text"
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            onBlur={handleRenameConfirm}
            onKeyDown={handleKeyDown}
            className="flex-1 min-w-0 bg-ink-700 border border-accent-400 rounded px-1 py-0.5 text-[12px] text-paper-100 focus:outline-none"
            autoFocus
          />
        ) : (
          <span className="text-[12px] truncate flex-1 min-w-0">{node.name}</span>
        )}
      </div>
    </div>
  )
}

export function FileExplorer({
  rootNodes,
  onFileSelect,
  onNewFile,
  onNewFolder,
  onDelete,
  onRename,
  className = '',
}: FileExplorerProps) {
  const [selectedPath, setSelectedPath] = useState<string | null>(null)
  const [showContextMenu, setShowContextMenu] = useState<{ x: number; y: number; node: FileNode } | null>(null)

  const handleFileSelect = (file: FileNode) => {
    setSelectedPath(file.path)
    onFileSelect(file)
  }

  useEffect(() => {
    const handleClickOutside = () => setShowContextMenu(null)
    document.addEventListener('click', handleClickOutside)
    return () => document.removeEventListener('click', handleClickOutside)
  }, [])

  return (
    <div className={`flex flex-col h-full bg-ink-800 border-r border-ink-600 ${className}`}>
      <div className="flex items-center justify-between h-8 px-2 border-b border-ink-600">
        <h3 className="label-xs text-paper-400 flex items-center gap-1.5">
          <FolderOpen className="h-3.5 w-3.5" />
          EXPLORER
        </h3>
        <div className="flex items-center gap-1">
          <button
            onClick={() => onNewFile()}
            className="p-1.5 rounded text-paper-400 hover:text-paper-100 hover:bg-ink-700 transition-colors"
            title="New File"
            aria-label="New File"
          >
            <Plus className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={() => onNewFolder()}
            className="p-1.5 rounded text-paper-400 hover:text-paper-100 hover:bg-ink-700 transition-colors"
            title="New Folder"
            aria-label="New Folder"
          >
            <Folder className="h-3.5 w-3.5" />
          </button>
          <button
            className="p-1.5 rounded text-paper-400 hover:text-paper-100 hover:bg-ink-700 transition-colors"
            title="Refresh"
            aria-label="Refresh"
          >
            <RefreshCw className="h-3.5 w-3.5" />
          </button>
          <button
            className="p-1.5 rounded text-paper-400 hover:text-paper-100 hover:bg-ink-700 transition-colors"
            title="More Actions"
            aria-label="More Actions"
          >
            <MoreHorizontal className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-1">
        {rootNodes.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-paper-500 gap-2">
            <Folder className="h-8 w-8 opacity-50" />
            <p className="text-[12px]">No folder opened</p>
            <button
              onClick={() => onNewFolder()}
              className="text-[12px] text-accent-400 hover:underline"
            >
              Open Folder
            </button>
          </div>
        ) : (
          rootNodes.map((node) => (
            <FileTreeNode
              key={node.id}
              node={node}
              depth={0}
              onFileSelect={handleFileSelect}
              onNewFile={onNewFile}
              onNewFolder={onNewFolder}
              onDelete={onDelete}
              onRename={onRename}
              selectedPath={selectedPath}
            />
          ))
        )}
      </div>

      {showContextMenu && (
        <div
          className="fixed z-50 glass rounded-lg border border-ink-600 p-1 shadow-lg min-w-[160px]"
          style={{ left: showContextMenu.x, top: showContextMenu.y }}
        >
          <button className="w-full flex items-center gap-2 px-2 py-1.5 rounded text-[12px] text-paper-300 hover:bg-ink-700 hover:text-paper-100">
            <Plus className="h-3.5 w-3.5" /> New File
          </button>
          <button className="w-full flex items-center gap-2 px-2 py-1.5 rounded text-[12px] text-paper-300 hover:bg-ink-700 hover:text-paper-100">
            <Folder className="h-3.5 w-3.5" /> New Folder
          </button>
          <hr className="border-ink-600 my-1" />
          <button className="w-full flex items-center gap-2 px-2 py-1.5 rounded text-[12px] text-conflict-400 hover:bg-conflict-500/10 hover:text-conflict-300">
            Delete
          </button>
        </div>
      )}
    </div>
  )
}

function generateMockFileTree(): FileNode[] {
  return [
    {
      id: '1',
      name: 'workspace',
      path: '/workspace',
      type: 'folder',
      expanded: true,
      children: [
        { id: '2', name: 'dataset.csv', path: '/workspace/dataset.csv', type: 'file', language: 'plaintext' },
        { id: '3', name: 'train.py', path: '/workspace/train.py', type: 'file', language: 'python' },
        { id: '4', name: 'config.yaml', path: '/workspace/config.yaml', type: 'file', language: 'yaml' },
        { id: '5', name: 'metrics.json', path: '/workspace/metrics.json', type: 'file', language: 'json' },
        {
          id: '6',
          name: 'src',
          path: '/workspace/src',
          type: 'folder',
          expanded: false,
          children: [
            { id: '7', name: 'model.py', path: '/workspace/src/model.py', type: 'file', language: 'python' },
            { id: '8', name: 'utils.py', path: '/workspace/src/utils.py', type: 'file', language: 'python' },
          ],
        },
        {
          id: '9',
          name: 'notebooks',
          path: '/workspace/notebooks',
          type: 'folder',
          expanded: false,
          children: [
            { id: '10', name: 'explore.ipynb', path: '/workspace/notebooks/explore.ipynb', type: 'file', language: 'json' },
          ],
        },
      ],
    },
  ]
}

export { generateMockFileTree }
export type { FileNode }