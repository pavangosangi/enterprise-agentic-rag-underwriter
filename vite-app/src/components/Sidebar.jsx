import { useState } from 'react'
import axios from 'axios'
import { CheckCircle2, XCircle, RefreshCw } from 'lucide-react'
import SidebarEvals from './SidebarEvals'

export default function Sidebar({ health, setHealth }) {
  const [loading, setLoading] = useState(false)

  const checkHealth = async () => {
    setLoading(true)
    try {
      const res = await axios.get('/api/health')
      setHealth({ status: 'success', data: res.data })
    } catch (err) {
      setHealth({ status: 'error' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <aside className="w-80 bg-gemini-surface border-r border-gemini-border flex flex-col z-20 shadow-[4px_0_24px_rgba(0,0,0,0.02)]">
      {/* Top half: Historical Logs */}
      <div className="flex-1 flex flex-col min-h-0">
         <SidebarEvals />
      </div>

      {/* Bottom half: System Health */}
      <div className="p-4 border-t border-gemini-border bg-gemini-surface shrink-0">
        <h2 className="text-xs font-semibold text-gemini-text-secondary uppercase tracking-wider mb-3">
          System Health
        </h2>
        <button 
          onClick={checkHealth}
          disabled={loading}
          className="w-full btn-secondary text-xs flex items-center justify-center gap-2 mb-3 py-2"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          Check Connectivity
        </button>

        {health && (
          <div className="space-y-1.5 animate-fade-in">
            {health.status === 'success' ? (
              <>
                <HealthStatus label="FastAPI" status="UP" success />
                <HealthStatus label="Qdrant" status={health.data.qdrant?.toUpperCase()} success={health.data.qdrant === 'up'} />
                <HealthStatus label="Ollama" status={health.data.ollama?.toUpperCase()} success={health.data.ollama === 'up'} />
              </>
            ) : (
              <HealthStatus label="FastAPI" status="DOWN" success={false} />
            )}
          </div>
        )}
      </div>
    </aside>
  )
}

function HealthStatus({ label, status, success }) {
  return (
    <div className={`flex items-center justify-between p-3 rounded-xl border ${success ? 'bg-green-50 border-green-100 text-green-700' : 'bg-red-50 border-red-100 text-red-700'}`}>
      <span className="text-sm font-medium">{label}</span>
      <div className="flex items-center gap-1.5">
        {success ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
        <span className="text-xs font-bold">{status}</span>
      </div>
    </div>
  )
}
