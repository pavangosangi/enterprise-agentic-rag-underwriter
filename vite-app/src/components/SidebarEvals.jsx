import { useState, useEffect } from 'react'
import axios from 'axios'
import { Activity, Clock, CheckCircle2, XCircle, RefreshCw, BarChart2 } from 'lucide-react'

export default function SidebarEvals() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(false)

  const fetchLogs = async () => {
    setLoading(true)
    try {
      const res = await axios.get('/api/eval_logs')
      setLogs((res.data.logs || []).reverse())
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchLogs()
    // Optionally poll every 10s or listen to an event
    const interval = setInterval(fetchLogs, 10000)
    return () => clearInterval(interval)
  }, [])

  // Aggregate stats
  const totalEvals = logs.length
  let totalMetrics = 0
  let passedMetrics = 0
  
  logs.forEach(log => {
    const results = Object.values(log.results || {})
    totalMetrics += results.length
    results.forEach(r => {
      if (r.passed) passedMetrics++
    })
  })
  
  const avgPassRate = totalMetrics > 0 ? Math.round((passedMetrics / totalMetrics) * 100) : 0

  return (
    <div className="w-80 shrink-0 h-full flex flex-col bg-gemini-surface border border-gemini-border rounded-2xl shadow-sm overflow-hidden animate-fade-in">
      <div className="p-4 border-b border-gemini-border bg-gemini-bg/50 shrink-0 flex items-center justify-between">
        <h3 className="text-sm font-medium text-gemini-text flex items-center gap-2">
          <Activity size={16} className="text-gemini-accent" />
          Evaluation History
        </h3>
        <button onClick={fetchLogs} className="text-gemini-text-secondary hover:text-gemini-text">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* Aggregate Stats */}
      <div className="grid grid-cols-2 gap-2 p-3 border-b border-gemini-border shrink-0 bg-gemini-surface">
        <div className="bg-gemini-bg p-2 rounded-lg border border-gemini-border flex flex-col items-center">
          <div className="text-[10px] font-bold uppercase text-gemini-text-secondary">Queries</div>
          <div className="text-lg font-light text-gemini-text">{totalEvals}</div>
        </div>
        <div className="bg-gemini-bg p-2 rounded-lg border border-gemini-border flex flex-col items-center">
          <div className="text-[10px] font-bold uppercase text-gemini-text-secondary">Pass Rate</div>
          <div className="text-lg font-light text-gemini-text">{avgPassRate}%</div>
        </div>
      </div>

      {/* Log List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {logs.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center text-gemini-text-secondary opacity-50 p-4">
            <BarChart2 size={32} className="mb-2" />
            <div className="text-xs">No evaluations yet. Run an inline evaluation to see history here.</div>
          </div>
        ) : (
          logs.map((log, idx) => (
            <div key={idx} className="bg-gemini-bg border border-gemini-border rounded-xl p-3 shadow-sm hover:border-gemini-text-secondary/30 transition-colors">
              <div className="text-[9px] text-gemini-text-secondary flex items-center gap-1.5 mb-1.5">
                <Clock size={10} />
                {new Date(log.timestamp).toLocaleString()}
              </div>
              <div className="text-xs font-medium text-gemini-text line-clamp-2 mb-2 leading-snug">
                Q: {log.query}
              </div>
              
              <div className="space-y-1.5 border-t border-gemini-border pt-2 mt-2">
                {Object.entries(log.results || {}).map(([metric, data], i) => (
                  <div key={i} className="flex flex-col gap-1">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-gemini-text-secondary truncate pr-2">{metric}</span>
                      <span className={`flex items-center gap-1 text-[9px] font-bold px-1.5 py-0.5 rounded ${data.passed ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}`}>
                        {data.passed ? <CheckCircle2 size={8} /> : <XCircle size={8} />}
                        {data.score.toFixed(1)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
