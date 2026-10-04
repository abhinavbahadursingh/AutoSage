import { useEffect } from 'react'
import { SandboxIDE } from '../components/workspace/SandboxIDE'

export function SandboxPage() {
  useEffect(() => {
    document.title = 'Sandbox | AutoSage'
  }, [])

  return (
    <div className="relative h-full" style={{ color: 'var(--as-text)' }}>
      <div className="h-full">
        <SandboxIDE />
      </div>
    </div>
  )
}