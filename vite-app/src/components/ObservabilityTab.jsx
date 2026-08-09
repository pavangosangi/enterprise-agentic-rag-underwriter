import { useState, useEffect } from 'react'
import axios from 'axios'
import { Activity, RefreshCw, Box, Server, Clock, Zap, ChevronDown, ChevronUp } from 'lucide-react'

export default function ObservabilityTab({ agentSteps, telemetry }) {
  const [traces, setTraces] = useState([])
  const [loading, setLoading] = useState(false)
  const [selectedSpan, setSelectedSpan] = useState(null)

  const fetchTraces = async () => {
    setLoading(true)
    try {
      const res = await axios.get('/api/traces')
      if (res.data.traces) {
        const grouped = {}
        res.data.traces.forEach(span => {
          const traceId = span.context?.trace_id || 'unknown'
          if (!grouped[traceId]) grouped[traceId] = []
          grouped[traceId].push(span)
        })
        
        const parsedTraces = []
        Object.keys(grouped).forEach(traceId => {
          const spans = grouped[traceId]
          const spanMap = {}
          const roots = []
          
          spans.forEach(s => {
            spanMap[s.context.span_id] = { ...s, children: [] }
          })
          
          spans.forEach(s => {
            if (s.parent_id && spanMap[s.parent_id]) {
              spanMap[s.parent_id].children.push(spanMap[s.context.span_id])
            } else {
              roots.push(spanMap[s.context.span_id])
            }
          })
          
          parsedTraces.push({ id: traceId, roots, allSpans: spans })
        })
        
        const filteredTraces = parsedTraces.filter(t => t.allSpans.length > 3)
        setTraces(filteredTraces.reverse().slice(0, 10))
      }
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchTraces()
  }, [])

  const obs = telemetry?.observability || {}
  const nodeLatencies = obs.node_latencies_ms || {}

  return (
    <div className="flex flex-col h-full animate-fade-in pb-4">
      {/* Header & Metrics Strip */}
      <div className="flex-shrink-0 mb-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-2xl font-medium text-gemini-text flex items-center gap-2">
              <Activity size={24} className="text-gemini-accent" />
              Observability Dashboard
            </h2>
            <p className="text-sm text-gemini-text-secondary mt-1">
              End-to-end visualization of your agent graph and LangSmith-style traces.
            </p>
          </div>
          <button onClick={fetchTraces} disabled={loading} className="btn-secondary flex items-center gap-2">
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            {loading ? 'Refreshing...' : 'Refresh Traces'}
          </button>
        </div>

        {telemetry && (
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-4">
            <MetricCard title="Total Steps" value={obs.total_steps_executed || 0} icon={Box} />
            {Object.entries(nodeLatencies).map(([node, lats], i) => {
              const val = Array.isArray(lats) ? lats.reduce((a,b)=>a+b,0) : lats;
              return (
                <MetricCard 
                  key={i} 
                  title={node} 
                  value={`${val} ms`} 
                  icon={Clock} 
                />
              )
            })}
          </div>
        )}
      </div>

      {/* Main 3-Column Workspace */}
      <div className="flex-1 flex gap-4 min-h-0">
        
        {/* Column 1: Trace Tree (25%) */}
        <div className="w-1/4 bg-gemini-surface border border-gemini-border rounded-2xl flex flex-col shadow-sm overflow-hidden">
          <div className="p-4 border-b border-gemini-border bg-gemini-bg/50 shrink-0">
             <h3 className="text-sm font-medium text-gemini-text uppercase tracking-wider flex items-center gap-2">
               <Server size={14} className="text-gemini-accent" />
               OpenTelemetry Trees
             </h3>
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            {traces.length === 0 ? (
              <div className="h-full flex items-center justify-center text-gemini-text-secondary text-sm">No traces found.</div>
            ) : (
              traces.map((trace, i) => (
                <CollapsibleTrace 
                  key={trace.id} 
                  trace={trace} 
                  defaultOpen={i === 0} 
                  selectedSpan={selectedSpan} 
                  setSelectedSpan={setSelectedSpan} 
                />
              ))
            )}
          </div>
        </div>
        
        {/* Column 2: Span Detail View (50%) */}
        <div className="w-2/4 bg-gemini-surface border border-gemini-border rounded-2xl flex flex-col shadow-sm overflow-hidden">
          {selectedSpan ? (
            <SpanDetail span={selectedSpan} />
          ) : (
            <div className="m-auto flex flex-col items-center justify-center text-gemini-text-secondary p-12">
              <Zap size={48} className="mb-4 opacity-20 text-amber-500" />
              <p>Select a span from the left tree to inspect its details</p>
            </div>
          )}
        </div>

        {/* Column 3: Execution Trace (25%) */}
        <div className="w-1/4 bg-gemini-surface border border-gemini-border rounded-2xl flex flex-col shadow-sm overflow-hidden">
          <div className="p-4 border-b border-gemini-border bg-gemini-bg/50 shrink-0">
             <h3 className="text-sm font-medium text-gemini-text uppercase tracking-wider flex items-center gap-2">
               <Activity size={14} className="text-emerald-500" />
               Agent Steps
             </h3>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {agentSteps && agentSteps.length > 0 ? (
              agentSteps.map((step, idx) => (
                <div key={idx} className="bg-gemini-bg border border-gemini-border rounded-xl overflow-hidden relative">
                  <div className="absolute top-0 left-0 bottom-0 w-1 bg-emerald-500/50"></div>
                  <div className="p-3 border-b border-gemini-border/50 bg-gemini-surface pl-4">
                    <span className="text-[10px] uppercase font-bold text-gemini-text-secondary">Step {idx + 1}</span>
                    <div className="font-mono text-sm text-gemini-text mt-0.5">{step.node}</div>
                  </div>
                  <div className="p-3 overflow-x-auto">
                    <pre className="text-[10px] font-mono text-amber-500">{JSON.stringify(step.state_update, null, 2)}</pre>
                  </div>
                </div>
              ))
            ) : (
              <div className="h-full flex items-center justify-center text-gemini-text-secondary text-sm text-center px-4">
                No state updates available. Interact with the Chat to populate.
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  )
}

function MetricCard({ title, value, icon: Icon }) {
  return (
    <div className="bg-gemini-surface border border-gemini-border rounded-xl p-4 flex items-center gap-4 shadow-sm">
      <div className="w-10 h-10 rounded-full bg-gemini-blue-light text-gemini-accent flex items-center justify-center shrink-0">
        <Icon size={18} />
      </div>
      <div className="overflow-hidden">
        <div className="text-[10px] font-bold uppercase text-gemini-text-secondary truncate">{title}</div>
        <div className="text-lg font-medium text-gemini-text">{value}</div>
      </div>
    </div>
  )
}

function CollapsibleTrace({ trace, defaultOpen, selectedSpan, setSelectedSpan }) {
  const [open, setOpen] = useState(defaultOpen);
  
  return (
    <div className="mb-4 bg-gemini-surface border border-gemini-border rounded-xl overflow-hidden shadow-sm">
      <button 
        className="w-full p-3 flex justify-between items-center hover:bg-gemini-bg transition-colors text-left"
        onClick={() => setOpen(!open)}
      >
        <span className="text-[10px] font-mono text-gemini-text-secondary truncate pr-2" title={trace.id}>
          Trace: {trace.id.substring(0, 16)}...
        </span>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-[9px] font-medium bg-gemini-blue-light text-gemini-accent px-1.5 py-0.5 rounded-full">
            {trace.allSpans.length} spans
          </span>
          {open ? <ChevronUp size={14} className="text-gemini-text-secondary" /> : <ChevronDown size={14} className="text-gemini-text-secondary" />}
        </div>
      </button>
      
      {open && (
        <div className="p-3 border-t border-gemini-border bg-gemini-bg/50">
          {trace.roots.map(root => (
            <SpanNode 
              key={root.context.span_id} 
              node={root} 
              selectedSpan={selectedSpan}
              setSelectedSpan={setSelectedSpan}
            />
          ))}
        </div>
      )}
    </div>
  )
}


function SpanNode({ node, selectedSpan, setSelectedSpan, level = 0 }) {
  const isSelected = selectedSpan?.context?.span_id === node.context?.span_id;
  
  const start = node.start_time ? Number(node.start_time) / 1000000 : null;
  const end = node.end_time ? Number(node.end_time) / 1000000 : null;
  const dur = start && end ? ((end - start) / 1000).toFixed(2) + 's' : '-';
  const type = node.attributes?.['openinference.span.kind'] || node.attributes?.['span.type'] || 'Span';
  
  return (
    <div className={`mt-0.5 ${level > 0 ? 'ml-3 pl-3 border-l border-gemini-border' : ''}`}>
      <div 
        className={`py-1.5 px-2 rounded-lg cursor-pointer transition-colors flex items-center justify-between ${
          isSelected 
            ? 'bg-amber-500/10 shadow-sm border border-amber-500/30' 
            : 'hover:bg-gemini-surface border border-transparent'
        }`}
        onClick={() => setSelectedSpan(node)}
      >
         <div className="flex items-center gap-2 overflow-hidden">
           <span className={`font-mono text-[9px] px-1.5 py-0.5 rounded border shrink-0 ${isSelected ? 'border-amber-500/30 text-amber-500 bg-amber-500/10' : 'border-gemini-border text-gemini-text-secondary bg-gemini-surface'}`}>
             {type}
           </span>
           <span className={`text-xs truncate ${isSelected ? 'font-medium text-amber-500' : 'text-gemini-text'}`} title={node.name}>{node.name}</span>
         </div>
         <div className="flex items-center gap-2 ml-2 shrink-0">
           {node.status?.status_code === 'ERROR' && (
             <span className="text-red-500 text-xs">⚠</span>
           )}
           <span className="text-[10px] text-gemini-text-secondary font-mono">{dur}</span>
         </div>
      </div>
      
      {node.children && node.children.length > 0 && (
        <div className="mt-0.5">
          {node.children.map(child => (
            <SpanNode 
              key={child.context.span_id} 
              node={child} 
              selectedSpan={selectedSpan} 
              setSelectedSpan={setSelectedSpan}
              level={level + 1}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function SpanDetail({ span }) {
  const start = span.start_time ? new Date(Number(span.start_time) / 1000000) : null
  const end = span.end_time ? new Date(Number(span.end_time) / 1000000) : null
  const dur = start && end ? ((end.getTime() - start.getTime()) / 1000).toFixed(2) + 's' : '-'
  
  const attrs = span.attributes || {}
  
  const parseJSONStr = (str) => {
    try {
      if (typeof str === 'string' && (str.startsWith('{') || str.startsWith('['))) {
        return JSON.parse(str)
      }
    } catch { /* ignore */ }
    return str
  }

  const inputs = parseJSONStr(attrs['input.value'] || attrs['langchain.run.inputs'] || attrs['input'] || attrs['inputs'] || null)
  const outputs = parseJSONStr(attrs['output.value'] || attrs['langchain.run.outputs'] || attrs['output'] || attrs['outputs'] || null)
  const errorMsg = attrs['exception.message'] || attrs['error'] || null
  const type = attrs['openinference.span.kind'] || attrs['span.type'] || 'Span'
  
  const renderCodeBlock = (data, isOutput = false) => {
    if (!data) return <div className="text-xs text-gemini-text-secondary italic">None</div>;
    const str = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
    return (
      <pre className={`text-xs font-mono whitespace-pre-wrap ${isOutput ? 'text-emerald-600 dark:text-emerald-400' : 'text-gemini-text'}`}>
        {str}
      </pre>
    )
  }

  return (
    <div className="flex flex-col h-full bg-gemini-bg overflow-hidden animate-fade-in">
      <div className="p-4 border-b border-gemini-border bg-gemini-surface shrink-0 flex items-center justify-between">
         <div className="flex items-center gap-3">
           <span className="text-amber-500 font-mono text-[10px] px-2 py-1 bg-amber-500/10 border border-amber-500/20 rounded">
             {type}
           </span>
           <h3 className="text-lg font-medium text-gemini-text truncate">{span.name}</h3>
         </div>
      </div>
      
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {errorMsg && (
          <div className="p-4 rounded-xl bg-red-50 border border-red-200 shadow-sm">
            <div className="text-red-700 font-medium text-sm mb-2 flex items-center gap-2">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              Error
            </div>
            <div className="text-red-600 text-xs font-mono whitespace-pre-wrap bg-red-100/50 p-3 rounded-lg border border-red-100">{errorMsg}</div>
          </div>
        )}
      
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 shrink-0">
           <div className="bg-gemini-surface p-3 rounded-xl border border-gemini-border shadow-sm">
             <div className="text-[9px] font-bold tracking-wider text-gemini-text-secondary/70 mb-1">START TIME</div>
             <div className="text-xs text-gemini-text">{start ? start.toLocaleString() : '-'}</div>
           </div>
           <div className="bg-gemini-surface p-3 rounded-xl border border-gemini-border shadow-sm">
             <div className="text-[9px] font-bold tracking-wider text-gemini-text-secondary/70 mb-1">END TIME</div>
             <div className="text-xs text-gemini-text">{end ? end.toLocaleString() : '-'}</div>
           </div>
           <div className="bg-gemini-surface p-3 rounded-xl border border-gemini-border shadow-sm">
             <div className="text-[9px] font-bold tracking-wider text-gemini-text-secondary/70 mb-1">LATENCY</div>
             <div className="text-xs text-amber-500 font-mono bg-amber-500/10 px-2 py-0.5 rounded inline-block">{dur}</div>
           </div>
           <div className="bg-gemini-surface p-3 rounded-xl border border-gemini-border shadow-sm">
             <div className="text-[9px] font-bold tracking-wider text-gemini-text-secondary/70 mb-1">STATUS</div>
             <div className={`text-xs font-medium inline-block px-2 py-0.5 rounded ${span.status?.status_code === 'ERROR' ? 'bg-red-100 text-red-600' : 'bg-emerald-100 text-emerald-700'}`}>
               {span.status?.status_code || 'OK'}
             </div>
           </div>
        </div>
        
        <div>
          <div className="text-[10px] font-bold tracking-wider text-gemini-text-secondary/70 mb-2 pl-1">INPUT</div>
          <div className="bg-gemini-surface p-4 rounded-xl border border-gemini-border shadow-sm overflow-x-auto">
            {renderCodeBlock(inputs, false)}
          </div>
        </div>

        <div>
          <div className="text-[10px] font-bold tracking-wider text-gemini-text-secondary/70 mb-2 pl-1">OUTPUT</div>
          <div className="bg-gemini-surface p-4 rounded-xl border border-emerald-500/30 shadow-sm overflow-x-auto bg-emerald-50/30">
            {renderCodeBlock(outputs, true)}
          </div>
        </div>
        
        <div className="opacity-50 hover:opacity-100 transition-opacity">
          <div className="text-[10px] font-bold tracking-wider text-gemini-text-secondary/70 mb-2 pl-1">RAW ATTRIBUTES</div>
          <div className="bg-gemini-surface p-4 rounded-xl border border-gemini-border overflow-x-auto">
            <pre className="text-[10px] font-mono text-gemini-text-secondary">
              {JSON.stringify(attrs, null, 2)}
            </pre>
          </div>
        </div>
      </div>
    </div>
  )
}
