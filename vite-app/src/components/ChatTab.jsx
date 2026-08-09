import { useState, useRef, useEffect } from 'react'
import axios from 'axios'
import { Send, Bot, User, ChevronDown, ChevronUp, Loader2, ArrowDown, Play } from 'lucide-react'
import ReactMarkdown from 'react-markdown'

export default function ChatTab({ onChatUpdate, selectedMetrics }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSend = async () => {
    if (!input.trim() || loading) return
    const userMsg = { role: 'user', content: input }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const res = await axios.post('/api/chat', { query: userMsg.content })
      const data = res.data
      
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.answer || 'No answer provided.',
        citations: data.citations || [],
        agent_steps: data.agent_steps || [],
        telemetry: data.evaluation_telemetry || {},
        query: userMsg.content,
        retrieved_contexts: data.retrieved_contexts || []
      }])

      if (onChatUpdate) {
        onChatUpdate(data.agent_steps || [], data.evaluation_telemetry || {})
      }
    } catch (err) {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Connection error.', isError: true }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full bg-gemini-surface rounded-2xl shadow-sm border border-gemini-border overflow-hidden">
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center opacity-50">
            <Bot size={48} className="mb-4 text-gemini-accent" />
            <h2 className="text-xl font-medium text-gemini-text">Hello, I'm your Underwriting Agent</h2>
            <p className="text-sm mt-2 max-w-sm">Ask me any questions about P&C underwriting policies, rules, and guidelines.</p>
          </div>
        ) : (
          messages.map((msg, i) => (
            <MessageBubble key={i} message={msg} selectedMetrics={selectedMetrics} />
          ))
        )}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-gemini-bot-bg rounded-2xl rounded-tl-sm p-4 text-gemini-text flex items-center gap-3">
              <Loader2 size={18} className="animate-spin text-gemini-accent" />
              <span className="text-sm font-medium">Analyzing...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 bg-gemini-surface border-t border-gemini-border">
        <div className="relative flex items-center">
          <textarea
            value={input}
            onChange={(e) => {
              setInput(e.target.value)
              e.target.style.height = 'auto'
              e.target.style.height = Math.min(e.target.scrollHeight, 150) + 'px'
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSend()
              }
            }}
            placeholder="Enter your underwriting question..."
            className="input-field pr-12 resize-none overflow-y-auto"
            rows={1}
            style={{ minHeight: '52px', maxHeight: '150px' }}
          />
          <button 
            onClick={handleSend}
            disabled={!input.trim() || loading}
            className="absolute right-2 p-2 bg-gemini-accent text-white rounded-xl hover:bg-blue-600 disabled:opacity-50 disabled:hover:bg-gemini-accent transition-colors"
          >
            <Send size={18} />
          </button>
        </div>
      </div>
    </div>
  )
}

function MessageBubble({ message }) {
  const isUser = message.role === 'user'
  
  return (
    <div className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'} animate-slide-up`}>
      <div className={`max-w-[80%] flex gap-4 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
        <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${isUser ? 'bg-gemini-user-bg text-gemini-text' : 'bg-gemini-blue-light text-gemini-accent'}`}>
          {isUser ? <User size={16} /> : <Bot size={16} />}
        </div>
        
        <div className={`flex flex-col gap-2 ${isUser ? 'items-end' : 'items-start'} w-full`}>
          {message.telemetry?.safety_eval && (
            <div className={`text-xs font-medium px-2 py-1 rounded-full ${message.telemetry.safety_eval.status === 'PASSED' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
              Safety Eval: {message.telemetry.safety_eval.status}
            </div>
          )}

          <div className={`px-5 py-3.5 rounded-2xl text-base leading-relaxed w-full ${
            isUser ? 'bg-gemini-user-bg text-gemini-text rounded-tr-sm' : 'bg-gemini-bot-bg text-gemini-text rounded-tl-sm'
          } ${message.isError ? 'bg-red-50 text-red-600 border border-red-100' : ''}`}>
            {isUser ? message.content : (
              <div className="prose max-w-none">
                <ReactMarkdown>{message.content}</ReactMarkdown>
              </div>
            )}
          </div>

          {!isUser && message.citations?.length > 0 && (
            <Expandable section="Sources">
              <ul className="list-disc pl-4 space-y-1 text-sm text-gemini-text-secondary">
                {message.citations.map((c, idx) => (
                  <li key={idx}><strong>{c.source_document}</strong> ({c.section_or_page})</li>
                ))}
              </ul>
            </Expandable>
          )}

          {!isUser && message.agent_steps?.length > 0 && (
            <Expandable section="Agent Reasoning & Steps">
              <div className="flex flex-col">
                {message.agent_steps.map((step, idx) => (
                  <div key={idx} className="relative flex items-center gap-3 py-1.5" style={{ paddingLeft: `${idx * 28}px` }}>
                    {/* Vertical connecting lines for preceding levels */}
                    {Array.from({ length: idx }).map((_, i) => (
                      <div key={i} className="absolute top-0 bottom-0 border-l border-gemini-border/80" style={{ left: `${(i * 28) + 14}px` }}></div>
                    ))}
                    {/* Horizontal notch */}
                    {idx > 0 && (
                      <div className="absolute top-1/2 -mt-[0.5px] border-t border-gemini-border/80 w-3.5" style={{ left: `${((idx - 1) * 28) + 14}px` }}></div>
                    )}
                    <span className="font-mono text-[9px] px-1.5 py-0.5 rounded border border-gemini-border/80 text-gemini-text-secondary bg-gemini-bg z-10 tracking-wider">
                      CHAIN
                    </span>
                    <span className="text-[13px] text-gemini-text z-10 tracking-wide">{step.node}</span>
                  </div>
                ))}
              </div>
            </Expandable>
          )}

          {!isUser && !message.isError && message.query && (
            <InlineEvals message={message} />
          )}
        </div>
      </div>
    </div>
  )
}

function Expandable({ section, children }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="w-full mt-1 bg-gemini-surface border border-gemini-border rounded-xl overflow-hidden shadow-sm">
      <button 
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-2.5 bg-gemini-surface hover:bg-gemini-bg transition-colors text-xs font-medium text-gemini-text-secondary"
      >
        {section}
        {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>
      {open && (
        <div className="p-4 border-t border-gemini-border bg-gemini-bg/30">
          {children}
        </div>
      )}
    </div>
  )
}

const AVAILABLE_METRICS = [
  "Faithfulness", "Answer Relevancy", 
  "Contextual Relevance", "Bias", "Toxicity",
  "Tool Chaining Reliability", "Identity Boundaries"
]

function InlineEvals({ message }) {
  const [expanded, setExpanded] = useState(false)
  const [selectedMetrics, setSelectedMetrics] = useState(["Faithfulness", "Answer Relevancy"])
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)

  const toggleMetric = (m) => {
    if (selectedMetrics.includes(m)) {
      setSelectedMetrics(selectedMetrics.filter(x => x !== m))
    } else {
      setSelectedMetrics([...selectedMetrics, m])
    }
  }

  const handleRun = async () => {
    if (selectedMetrics.length === 0) return
    setLoading(true)
    setError(null)
    setResults(null)
    
    try {
      const res = await axios.post('/api/evaluate', {
        query: message.query,
        actual_output: message.content,
        retrieval_context: message.retrieved_contexts || [],
        requested_metrics: selectedMetrics,
        agent_steps: message.agent_steps || []
      })
      setResults(res.data.results || {})
    } catch (err) {
      setError(err.response?.data?.detail || err.message || "Connection error")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="w-full mt-2">
      {!expanded ? (
        <button 
          onClick={() => setExpanded(true)}
          className="btn-secondary text-[11px] flex items-center gap-1.5 py-1.5 px-3 bg-gemini-blue-light text-gemini-accent border-none rounded-lg hover:bg-blue-100 transition-colors"
        >
          <Play size={10} className="fill-current" />
          Run DeepEval
        </button>
      ) : (
        <div className="bg-gemini-surface border border-gemini-border rounded-xl p-4 shadow-sm animate-fade-in w-full">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-medium text-gemini-text flex items-center gap-2">
              <Play size={14} className="text-gemini-accent fill-current" />
              Evaluation Setup
            </h4>
            <button onClick={() => setExpanded(false)} className="text-gemini-text-secondary hover:text-gemini-text">
              <ChevronUp size={14} />
            </button>
          </div>
          
          <div className="mb-4">
            <div className="text-[11px] text-gemini-text-secondary mb-2 font-medium">Select Metrics:</div>
            <div className="flex flex-wrap gap-1.5">
              {AVAILABLE_METRICS.map(m => (
                <button
                  key={m}
                  onClick={() => toggleMetric(m)}
                  className={`text-[9px] px-2 py-1 rounded-full border transition-colors ${
                    selectedMetrics.includes(m)
                      ? 'bg-gemini-accent text-white border-gemini-accent'
                      : 'bg-gemini-bg text-gemini-text-secondary border-gemini-border hover:border-gemini-text-secondary/30'
                  }`}
                >
                  {m}
                </button>
              ))}
            </div>
          </div>
          
          {error && <div className="text-red-500 text-xs mb-3 p-2 bg-red-50 rounded-lg">{error}</div>}
          
          {results ? (
            <div className="mt-4">
              <div className="text-xs font-medium text-gemini-text-secondary mb-2 border-t border-gemini-border pt-3">Results:</div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {Object.entries(results).map(([metric, data]) => (
                  <div key={metric} className="bg-gemini-bg p-3 rounded-lg border border-gemini-border flex flex-col">
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs font-medium text-gemini-text">{metric}</span>
                      <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${data.passed ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}`}>
                        {data.passed ? 'PASS' : 'FAIL'} ({data.score.toFixed(1)}/3.0)
                      </span>
                    </div>
                    <div className="text-[10px] text-gemini-text-secondary leading-relaxed flex-1">
                      {data.reason}
                    </div>
                  </div>
                ))}
              </div>
              <button onClick={() => setResults(null)} className="w-full btn-secondary text-[11px] mt-3 py-1.5">
                Run Again
              </button>
            </div>
          ) : (
            <button 
              onClick={handleRun} 
              disabled={loading || selectedMetrics.length === 0}
              className="w-full btn-primary text-[11px] flex justify-center items-center gap-2 py-2"
            >
              {loading ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} className="fill-current" />}
              {loading ? 'Evaluating...' : 'Run Selected Metrics'}
            </button>
          )}
        </div>
      )}
    </div>
  )
}
