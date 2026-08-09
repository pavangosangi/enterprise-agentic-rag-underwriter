import { useState } from 'react'
import { Zap, Play, Loader2 } from 'lucide-react'

export default function DeepMCPTab() {
  const [formData, setFormData] = useState({
    query: '',
    actual_output: '',
    retrieval_context: '',
    expected_output: ''
  })
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)

  const handleRun = async () => {
    if (!formData.query || !formData.actual_output || !formData.retrieval_context) {
      setError("Please fill out query, answer, and contexts.")
      return
    }
    
    setLoading(true)
    setError(null)
    setResults({})
    
    try {
      const contexts = formData.retrieval_context.split('\n').map(c => c.trim()).filter(c => c)
      
      const es = new EventSource('/mcp/sse')
      
      const postUrl = await new Promise((resolve, reject) => {
        es.addEventListener('endpoint', (e) => {
          let url = e.data
          try {
             const parsed = new URL(url)
             url = '/mcp' + parsed.pathname + parsed.search
          } catch {
             url = '/mcp' + url
          }
          resolve(url)
        })
        es.onerror = () => reject(new Error("Failed to connect to MCP SSE stream."))
      })
      
      let messageId = 1
      const pendingRequests = new Map()
      
      es.addEventListener('message', (e) => {
        const data = JSON.parse(e.data)
        if (data.id && pendingRequests.has(data.id)) {
          pendingRequests.get(data.id)(data)
          pendingRequests.delete(data.id)
        }
      })
      
      const sendRequest = async (method, params) => {
        const id = messageId++
        return new Promise((resolve, reject) => {
          pendingRequests.set(id, (response) => {
            if (response.error) reject(new Error(response.error.message || "MCP Error"))
            else resolve(response.result)
          })
          fetch(postUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ jsonrpc: "2.0", id, method, params })
          }).catch(reject)
        })
      }
      
      const sendNotification = async (method, params) => {
        return fetch(postUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ jsonrpc: "2.0", method, params })
        })
      }
      
      await sendRequest("initialize", {
        protocolVersion: "2024-11-05",
        capabilities: {},
        clientInfo: { name: "react-ui", version: "1.0" }
      })
      
      await sendNotification("notifications/initialized", {})
      
      const f_res = await sendRequest("tools/call", {
        name: "evaluate_faithfulness",
        arguments: {
          input_text: formData.query,
          actual_output: formData.actual_output,
          retrieval_context: contexts
        }
      })
      
      const ar_res = await sendRequest("tools/call", {
        name: "evaluate_answer_relevancy",
        arguments: {
          input_text: formData.query,
          actual_output: formData.actual_output
        }
      })
      
      const cp_res = await sendRequest("tools/call", {
        name: "evaluate_contextual_precision",
        arguments: {
          input_text: formData.query,
          actual_output: formData.actual_output,
          expected_output: formData.expected_output || "N/A",
          retrieval_context: contexts
        }
      })
      
      const newResults = {}
      
      const parseResult = (toolResult, title) => {
        try {
          const content = toolResult.content[0].text
          const res = JSON.parse(content)
          newResults[title] = { score: res.score, passed: res.is_successful, reason: res.reason }
        } catch (err) {
          console.error("Failed to parse tool result:", toolResult, err)
        }
      }
      
      parseResult(f_res, "Faithfulness")
      parseResult(ar_res, "Answer Relevancy")
      parseResult(cp_res, "Contextual Precision")
      
      setResults(newResults)
      es.close()
    } catch (err) {
      setError(err.message || "Connection error")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      {loading && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center animate-fade-in">
          <div className="bg-gemini-surface p-8 rounded-3xl shadow-2xl flex flex-col items-center gap-4 max-w-sm w-full mx-4 border border-gemini-border">
            <Loader2 size={48} className="animate-spin text-amber-500" />
            <h3 className="text-xl font-medium text-gemini-text text-center">Running DeepMCP</h3>
            <p className="text-sm text-gemini-text-secondary text-center">Please wait while the evaluation metrics are processed via MCP...</p>
          </div>
        </div>
      )}
      <div className="bg-gemini-surface p-6 rounded-2xl shadow-sm border border-gemini-border">
        <h2 className="text-xl font-medium text-gemini-text mb-2 flex items-center gap-2">
          <Zap size={20} className="text-amber-500" />
          DeepMCP Evaluations
        </h2>
        <p className="text-sm text-gemini-text-secondary mb-6">Run DeepEval metrics directly. Testing containerized endpoints.</p>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1 ml-1 text-gemini-text-secondary">Question</label>
            <input type="text" className="input-field" value={formData.query} onChange={e => setFormData({...formData, query: e.target.value})} />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1 ml-1 text-gemini-text-secondary">Generated Answer</label>
            <textarea rows={3} className="input-field resize-none" value={formData.actual_output} onChange={e => setFormData({...formData, actual_output: e.target.value})} />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1 ml-1 text-gemini-text-secondary">Retrieved Contexts (one per line)</label>
            <textarea rows={3} className="input-field resize-none" value={formData.retrieval_context} onChange={e => setFormData({...formData, retrieval_context: e.target.value})} />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1 ml-1 text-gemini-text-secondary">Expected Answer (Ground Truth)</label>
            <textarea rows={2} className="input-field resize-none" value={formData.expected_output} onChange={e => setFormData({...formData, expected_output: e.target.value})} />
          </div>

          {error && <div className="text-amber-600 text-sm font-medium p-3 bg-amber-50 border border-amber-100 rounded-xl">{error}</div>}

          <div className="pt-2">
            <button onClick={handleRun} disabled={loading} className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-amber-500 text-white rounded-full hover:bg-amber-600 transition-colors font-medium">
              {loading ? <Loader2 size={18} className="animate-spin" /> : <Play size={18} />}
              {loading ? "Connecting..." : "Run DeepMCP Evaluation"}
            </button>
          </div>
        </div>
      </div>
      
      {results && Object.keys(results).length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 animate-fade-in">
          {Object.entries(results).map(([metric, data]) => (
            <div key={metric} className="bg-gemini-surface p-5 rounded-2xl shadow-sm border border-amber-500/20">
              <div className="text-sm font-medium text-amber-700 mb-1">{metric}</div>
              <div className="text-3xl font-light text-gemini-text mb-3">{data.score?.toFixed(2)}</div>
              <div className={`text-xs font-medium inline-block px-2 py-1 rounded-full mb-3 ${data.passed ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                {data.passed ? 'PASSED' : 'FAILED'}
              </div>
              <div className="text-xs text-gemini-text-secondary bg-gemini-bg p-3 rounded-xl border border-gemini-border">
                {data.reason || "No reasoning provided."}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
