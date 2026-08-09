import { useState } from 'react'
import axios from 'axios'
import { Play, Loader2 } from 'lucide-react'

export default function EvalsTab() {
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
    setResults(null)
    
    try {
      const contexts = formData.retrieval_context.split('\n').map(c => c.trim()).filter(c => c)
      const res = await axios.post('/api/evaluate', {
        query: formData.query,
        actual_output: formData.actual_output,
        retrieval_context: contexts,
        expected_output: formData.expected_output.trim() || null,
        requested_metrics: ["Faithfulness", "Answer Relevancy", "Contextual Precision", "Contextual Recall"],
        agent_steps: []
      })
      
      setResults(res.data.results || {})
    } catch (err) {
      setError(err.response?.data?.detail || err.message || "Connection error")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      {loading && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center animate-fade-in">
          <div className="bg-gemini-surface p-8 rounded-3xl shadow-2xl flex flex-col items-center gap-4 max-w-sm w-full mx-4 border border-gemini-border">
            <Loader2 size={48} className="animate-spin text-gemini-accent" />
            <h3 className="text-xl font-medium text-gemini-text text-center">Processing Evaluation</h3>
            <p className="text-sm text-gemini-text-secondary text-center">Please wait while Gemini analyzes the response...</p>
          </div>
        </div>
      )}
      <div className="bg-gemini-surface p-6 rounded-2xl shadow-sm border border-gemini-border">
        <h2 className="text-xl font-medium text-gemini-text mb-2">DeepEval Agent Evaluation</h2>
        <p className="text-sm text-gemini-text-secondary mb-6">Run a live evaluation on a QA pair using Gemini 3.1 Pro.</p>

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
            <label className="block text-sm font-medium mb-1 ml-1 text-gemini-text-secondary">Expected Answer (Ground Truth) [Optional]</label>
            <textarea rows={2} className="input-field resize-none" value={formData.expected_output} onChange={e => setFormData({...formData, expected_output: e.target.value})} />
          </div>

          {error && <div className="text-red-500 text-sm font-medium p-3 bg-red-50 rounded-xl">{error}</div>}

          <div className="pt-2">
            <button onClick={handleRun} disabled={loading} className="btn-primary flex items-center gap-2 w-full justify-center py-3">
              {loading ? <Loader2 size={18} className="animate-spin" /> : <Play size={18} />}
              {loading ? "Running Evaluation..." : "Run Evaluation"}
            </button>
          </div>
        </div>
      </div>

      {results && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 animate-fade-in">
          {Object.entries(results).map(([metric, data]) => (
            <div key={metric} className="bg-gemini-surface p-5 rounded-2xl shadow-sm border border-gemini-border">
              <div className="text-sm font-medium text-gemini-text-secondary mb-1">{metric}</div>
              <div className="text-3xl font-light text-gemini-text mb-3">{data.score?.toFixed(2)}</div>
              {data.passed !== undefined && (
                <div className={`text-xs font-medium inline-block px-2 py-1 rounded-full mb-3 ${data.passed ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                  {data.passed ? 'PASSED' : 'FAILED'}
                </div>
              )}
              <div className="text-xs text-gemini-text-secondary bg-gemini-bg p-3 rounded-xl border border-gemini-border">
                {data.reason}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
