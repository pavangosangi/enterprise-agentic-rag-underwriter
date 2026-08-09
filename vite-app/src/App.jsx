import { useState, useEffect } from 'react'
import { MessageSquare, BarChart2, Activity, Settings, Zap } from 'lucide-react'
import ChatTab from './components/ChatTab'
import EvalsTab from './components/EvalsTab'
import ObservabilityTab from './components/ObservabilityTab'
import DeepMCPTab from './components/DeepMCPTab'
import Sidebar from './components/Sidebar'

function App() {
  const [activeTab, setActiveTab] = useState('chat')
  const [health, setHealth] = useState(null)
  const [latestTelemetry, setLatestTelemetry] = useState(null)
  const [latestAgentSteps, setLatestAgentSteps] = useState(null)
  
  const tabs = [
    { id: 'chat', label: 'Chat', icon: MessageSquare },
    { id: 'evals', label: 'Evals', icon: BarChart2 },
    { id: 'observability', label: 'Observability', icon: Activity },
    { id: 'deepmcp', label: 'DeepMCP Evals', icon: Zap },
  ]

  return (
    <div className="flex h-screen overflow-hidden bg-gemini-bg">
      <Sidebar health={health} setHealth={setHealth} />
      
      <main className="flex-1 flex flex-col h-full overflow-hidden relative">
        <header className="px-8 py-4 bg-gemini-surface border-b border-gemini-border flex items-center justify-between z-10">
          <h1 className="text-xl font-medium flex items-center gap-2">
            <span className="text-2xl">🛡️</span> P&C Underwriting Agent
          </h1>
          
          <div className="flex bg-gemini-bg p-1 rounded-full border border-gemini-border">
            {tabs.map(tab => {
              const Icon = tab.icon
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-all ${
                    activeTab === tab.id 
                      ? 'bg-gemini-surface shadow-sm text-gemini-accent' 
                      : 'text-gemini-text-secondary hover:text-gemini-text hover:bg-black/5'
                  }`}
                >
                  <Icon size={16} />
                  {tab.label}
                </button>
              )
            })}
          </div>
        </header>

        <div className="flex-1 overflow-auto p-6 relative">
          <div className="w-full mx-auto h-full flex flex-col animate-fade-in">
            <div className={`h-full mx-auto w-full ${activeTab === 'chat' ? 'block max-w-7xl' : 'hidden'}`}>
              <ChatTab onChatUpdate={(steps, tele) => { setLatestAgentSteps(steps); setLatestTelemetry(tele); }} />
            </div>
            <div className={`h-full mx-auto w-full ${activeTab === 'evals' ? 'block max-w-5xl' : 'hidden'}`}>
              <EvalsTab />
            </div>
            <div className={`h-full w-full ${activeTab === 'observability' ? 'block max-w-[1800px] mx-auto' : 'hidden'}`}>
              <ObservabilityTab agentSteps={latestAgentSteps} telemetry={latestTelemetry} />
            </div>
            <div className={`h-full mx-auto w-full ${activeTab === 'deepmcp' ? 'block max-w-5xl' : 'hidden'}`}>
              <DeepMCPTab />
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

export default App
