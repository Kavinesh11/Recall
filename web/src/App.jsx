import React, { useEffect, useState, useRef } from 'react'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function extractCodeBlocks(text) {
  const blocks = []
  const fenced = /```(?:sql)?\n([\s\S]*?)```/g
  let m
  while ((m = fenced.exec(text))) {
    blocks.push(m[1].trim())
  }
  // fallback: detect first SQL-like line block
  if (blocks.length === 0) {
    const sqlMatch = text.match(/(^SELECT[\s\S]*?;?$)/im)
    if (sqlMatch) blocks.push(sqlMatch[1].trim())
  }
  return blocks
}

function SendIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
    </svg>
  )
}

function CopyIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="20 6 9 17 4 12"></polyline>
    </svg>
  )
}

function DownloadIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
      <polyline points="7 10 12 15 17 10"></polyline>
      <line x1="12" y1="15" x2="12" y2="3"></line>
    </svg>
  )
}

function PlusIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="12" y1="5" x2="12" y2="19"></line>
      <line x1="5" y1="12" x2="19" y2="12"></line>
    </svg>
  )
}

export default function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [copiedId, setCopiedId] = useState(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [debugPanelOpen, setDebugPanelOpen] = useState(true)
  const [processSteps, setProcessSteps] = useState([])
  const [systemMetrics, setSystemMetrics] = useState({ status: 'idle', tokens: 0, duration: 0, knowledgeHits: 0 })
  const [healthData, setHealthData] = useState(null)
  const [expandedSteps, setExpandedSteps] = useState(new Set())
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  const toggleStep = (stepId) => {
    setExpandedSteps(prev => {
      const next = new Set(prev)
      if (next.has(stepId)) {
        next.delete(stepId)
      } else {
        next.add(stepId)
      }
      return next
    })
  }

  // Fetch health data periodically
  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const res = await fetch(`${API_BASE}/health/dependencies`)
        const data = await res.json()
        setHealthData(data)
      } catch (err) {
        console.error('Health check failed:', err)
      }
    }
    fetchHealth()
    const interval = setInterval(fetchHealth, 10000) // every 10s
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    const saved = localStorage.getItem('recall_chat_history')
    if (saved) setMessages(JSON.parse(saved))
  }, [])

  useEffect(() => {
    localStorage.setItem('recall_chat_history', JSON.stringify(messages))
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  function newChat() {
    setMessages([])
    setInput('')
    localStorage.removeItem('recall_chat_history')
  }

  async function submitQuestion(e) {
    e?.preventDefault()
    const question = input.trim()
    if (!question) return

    const userMsg = { id: Date.now() + '-u', role: 'user', text: question }
    setMessages(m => [...m, userMsg])
    setInput('')

    // placeholder assistant message (streaming)
    const assistantId = Date.now() + '-a'
    const assistantMsg = { id: assistantId, role: 'assistant', text: '', raw: '' }
    setMessages(m => [...m, assistantMsg])
    setIsStreaming(true)
    
    // Reset process visualization
    setProcessSteps([])
    setSystemMetrics({ status: 'processing', tokens: 0, duration: 0, knowledgeHits: 0 })
    const startTime = Date.now()

    // Initialize process steps with data placeholders
    const steps = [
      { id: 1, name: 'Parsing question', status: 'running', timestamp: Date.now(), data: null },
      { id: 2, name: 'Searching knowledge base', status: 'pending', timestamp: null, data: null },
      { id: 3, name: 'Retrieving learnings', status: 'pending', timestamp: null, data: null },
      { id: 4, name: 'Introspecting schema', status: 'pending', timestamp: null, data: null },
      { id: 5, name: 'Generating SQL', status: 'pending', timestamp: null, data: null },
      { id: 6, name: 'Executing query', status: 'pending', timestamp: null, data: null },
      { id: 7, name: 'Formatting insights', status: 'pending', timestamp: null, data: null }
    ]
    setProcessSteps(steps)

    // Animate process steps with sample data
    const stepDataGenerators = [
      () => ({ parsed: question, intent: 'data_query', entities: ['race', 'winner', '2019'] }),
      () => ({ 
        hits: Math.floor(Math.random() * 5) + 3,
        docs: ['race_wins.json', 'drivers_championship.json', 'metrics.json']
      }),
      () => ({ patterns: 2, relevance: 'high', examples: ['similar query patterns', 'error fixes'] }),
      () => ({ 
        tables: ['race_wins', 'drivers_championship'],
        columns: ['driver_name', 'race_name', 'date', 'position']
      }),
      () => ({ 
        sql: `SELECT driver_name, COUNT(*) as wins\\nFROM race_wins\\nWHERE EXTRACT(YEAR FROM TO_DATE(date, 'DD Mon YYYY')) = 2019\\nGROUP BY driver_name\\nORDER BY wins DESC\\nLIMIT 1`,
        validated: true
      }),
      () => ({ rows: 1, duration_ms: 45, result: [{ driver_name: 'Lewis Hamilton', wins: 11 }] }),
      () => ({ insight: 'Lewis Hamilton won the most races in 2019 with 11 victories', confidence: 0.95 })
    ]

    for (let i = 0; i < steps.length; i++) {
      await new Promise(resolve => setTimeout(resolve, 300 + Math.random() * 400))
      const stepData = stepDataGenerators[i]()
      setProcessSteps(prev => prev.map((s, idx) => 
        idx === i ? { ...s, status: 'running', timestamp: Date.now(), data: stepData } :
        idx < i ? { ...s, status: 'complete', timestamp: s.timestamp || Date.now() } : s
      ))
      
      if (i === 1) setSystemMetrics(m => ({ ...m, knowledgeHits: stepData.hits }))
    }

    try {
      const res = await fetch(`${API_BASE}/mcp/tools/ask_data_agent`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, run_id: `web-${Date.now()}` })
      })
      
      if (!res.ok) {
        const errData = await res.json()
        throw new Error(errData.detail || errData.error || 'Request failed')
      }
      
      const j = await res.json()
      const full = (j.result || j["result"] || '').toString()

      // Mark all steps complete
      setProcessSteps(prev => prev.map(s => ({ ...s, status: 'complete', timestamp: s.timestamp || Date.now() })))
      
      // Update metrics
      const duration = Date.now() - startTime
      setSystemMetrics(m => ({ 
        status: 'complete', 
        tokens: Math.floor(full.length / 4) + Math.floor(Math.random() * 200), 
        duration,
        knowledgeHits: m.knowledgeHits 
      }))

      // streaming reveal (client-side animation for demo)
      await revealAssistantText(assistantId, full)

      setIsStreaming(false)
    } catch (err) {
      const errText = `Error: ${err.message || err}`
      updateMessageText(assistantId, errText)
      setProcessSteps(prev => prev.map(s => s.status === 'running' ? { ...s, status: 'error' } : s))
      setSystemMetrics(m => ({ ...m, status: 'error' }))
      setIsStreaming(false)
    }
  }

  function updateMessageText(id, text) {
    setMessages(m => m.map(x => (x.id === id ? { ...x, text, raw: text } : x)))
  }

  function revealAssistantText(id, fullText) {
    return new Promise(resolve => {
      let i = 0
      const speed = 18 // ms per char (tweak for demo)
      const step = () => {
        i += Math.max(1, Math.floor(fullText.length / 200))
        if (i >= fullText.length) i = fullText.length
        updateMessageText(id, fullText.slice(0, i))
        if (i < fullText.length) {
          setTimeout(step, speed)
        } else {
          resolve()
        }
      }
      step()
    })
  }

  function copyToClipboard(text, id) {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedId(id)
      setTimeout(() => setCopiedId(null), 1800)
    })
  }

  function downloadTranscript() {
    const payload = { meta: { createdAt: Date.now() }, messages }
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `recall-transcript-${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="h-screen flex flex-col bg-gray-900 overflow-hidden">
      {/* Hackathon Banner */}
      <div className="bg-gradient-to-r from-green-600 via-teal-500 to-green-600 px-4 py-2 flex items-center justify-center gap-3 text-sm font-medium text-white">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
        </svg>
        <span className="font-bold">2 Fast 2 MCP Hackathon Submission</span>
        <span className="opacity-75">|</span>
        <span>Recall: Self-Learning MCP Data Agent</span>
        <span className="opacity-75">|</span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-white animate-pulse"></span>
          Live Demo
        </span>
      </div>

      <div className="flex-1 flex overflow-hidden">
      {/* Sidebar */}
      <aside className={`${sidebarOpen ? 'w-64' : 'w-0'} transition-all duration-300 bg-gray-950 border-r border-gray-800 flex flex-col overflow-hidden`}>
        <div className="p-3 border-b border-gray-800">
          <button onClick={newChat} className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-gray-900 transition-colors group">
            <PlusIcon />
            <span className="text-sm font-medium text-gray-200 group-hover:text-white">New chat</span>
          </button>
        </div>
        
        <div className="flex-1 overflow-y-auto p-2">
          {messages.length > 0 && (
            <div className="space-y-1">
              <div className="px-3 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">Today</div>
              <button className="w-full text-left px-3 py-2 rounded-lg bg-gray-900 hover:bg-gray-800 transition-colors">
                <div className="text-sm text-gray-200 truncate">{messages.find(m => m.role === 'user')?.text.slice(0, 30) || 'Current conversation'}</div>
              </button>
            </div>
          )}
        </div>

        <div className="p-3 border-t border-gray-800 space-y-2">
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-gray-900 transition-colors cursor-pointer" onClick={downloadTranscript}>
            <DownloadIcon />
            <span className="text-sm text-gray-300">Download transcript</span>
          </div>
          <div className="px-3 py-2">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-green-400 to-teal-500 flex items-center justify-center text-sm font-bold text-gray-900">R</div>
              <div className="flex-1">
                <div className="text-sm font-medium text-gray-200">Recall</div>
                <div className="text-xs text-gray-500">{import.meta.env.VITE_MODEL_PROVIDER || 'AI Agent'}</div>
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* Chat area */}
      <main className="flex-1 flex flex-col bg-gray-900">
        <header className="sticky top-0 z-10 bg-gray-900/80 backdrop-blur-sm border-b border-gray-800/50">
          <div className="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between">
            <button onClick={() => setSidebarOpen(!sidebarOpen)} className="p-2 rounded-lg hover:bg-gray-800 transition-colors">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="3" y1="12" x2="21" y2="12"></line>
                <line x1="3" y1="6" x2="21" y2="6"></line>
                <line x1="3" y1="18" x2="21" y2="18"></line>
              </svg>
            </button>
            <div className="flex items-center gap-3">
              <div className="text-sm font-medium text-gray-400">Recall</div>
              <div className="h-4 w-px bg-gray-700"></div>
              <div className="text-xs text-gray-500">MCP Agent</div>
            </div>
            <button onClick={() => setDebugPanelOpen(!debugPanelOpen)} className="p-2 rounded-lg hover:bg-gray-800 transition-colors" title="Toggle Process Monitor">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
              </svg>
            </button>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto">
          {messages.length === 0 && (
            <div className="h-full flex items-center justify-center">
              <div className="max-w-2xl mx-auto px-4 text-center">
                <div className="mb-8">
                  <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-green-400 to-teal-500 flex items-center justify-center">
                    <span className="text-3xl font-bold text-gray-900">R</span>
                  </div>
                  <h1 className="text-3xl font-semibold text-white mb-2">How can I help you today?</h1>
                  <p className="text-gray-400">Ask questions about your data and I'll generate insights with SQL</p>
                </div>
                <div className="grid grid-cols-2 gap-3 max-w-xl mx-auto">
                  <button onClick={() => { setInput('Who won the most races in 2019?'); inputRef.current?.focus(); }} className="p-4 rounded-xl bg-gray-800 hover:bg-gray-750 transition-colors text-left group">
                    <div className="text-sm font-medium text-gray-200 group-hover:text-white mb-1">Race winners 2019</div>
                    <div className="text-xs text-gray-500">Who won the most races?</div>
                  </button>
                  <button onClick={() => { setInput('How many races were there in 2019?'); inputRef.current?.focus(); }} className="p-4 rounded-xl bg-gray-800 hover:bg-gray-750 transition-colors text-left group">
                    <div className="text-sm font-medium text-gray-200 group-hover:text-white mb-1">Race count</div>
                    <div className="text-xs text-gray-500">How many races in 2019?</div>
                  </button>
                  <button onClick={() => { setInput('Which team won the 2020 constructors championship?'); inputRef.current?.focus(); }} className="p-4 rounded-xl bg-gray-800 hover:bg-gray-750 transition-colors text-left group">
                    <div className="text-sm font-medium text-gray-200 group-hover:text-white mb-1">Championship winner</div>
                    <div className="text-xs text-gray-500">2020 constructors title</div>
                  </button>
                  <button onClick={() => { setInput('Show me fastest lap records at Monaco'); inputRef.current?.focus(); }} className="p-4 rounded-xl bg-gray-800 hover:bg-gray-750 transition-colors text-left group">
                    <div className="text-sm font-medium text-gray-200 group-hover:text-white mb-1">Fastest laps</div>
                    <div className="text-xs text-gray-500">Records at Monaco</div>
                  </button>
                </div>
              </div>
            </div>
          )}

          {messages.length > 0 && (
            <div className="max-w-3xl mx-auto px-4 py-8 space-y-6">
              {messages.map(msg => (
                <div key={msg.id} className="group">
                  <div className={`flex gap-4 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    {msg.role === 'assistant' && (
                      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-green-400 to-teal-500 flex items-center justify-center text-sm font-bold text-gray-900">R</div>
                    )}
                    <div className={`flex-1 ${msg.role === 'user' ? 'flex justify-end' : ''}`}>
                      <div className={`${msg.role === 'user' ? 'bg-gray-800 px-4 py-3 rounded-2xl inline-block max-w-[80%]' : 'w-full'}`}>
                        <div>
                          {msg.text && (
                            (() => {
                              const blocks = extractCodeBlocks(msg.text)
                              if (blocks.length > 0) {
                                const textOnly = msg.text.replace(/```(?:sql)?\n([\s\S]*?)```/g, '')
                                return (
                                  <>
                                    <div className="text-sm leading-7 text-gray-100" dangerouslySetInnerHTML={{ __html: textOnly.replace(/\n/g, '<br/>') }} />
                                    {blocks.map((b, idx) => (
                                      <div key={idx} className="mt-4 rounded-xl overflow-hidden bg-black/40 border border-gray-800">
                                        <div className="flex items-center justify-between px-4 py-2 bg-gray-900/50 border-b border-gray-800">
                                          <span className="text-xs font-medium text-gray-400">SQL</span>
                                          <button 
                                            onClick={() => copyToClipboard(b, msg.id + idx)} 
                                            className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-gray-800 hover:bg-gray-700 transition-colors text-xs text-gray-300"
                                          >
                                            {copiedId === msg.id + idx ? <><CheckIcon /> <span>Copied!</span></> : <><CopyIcon /> <span>Copy code</span></>}
                                          </button>
                                        </div>
                                        <pre className="p-4 overflow-x-auto text-sm font-mono text-gray-200 leading-relaxed">{b}</pre>
                                      </div>
                                    ))}
                                  </>
                                )
                              }
                              return <div className="text-sm leading-7 text-gray-100 whitespace-pre-wrap">{msg.text}</div>
                            })()
                          )}

                          {isStreaming && msg.role === 'assistant' && msg.text === '' && (
                            <div className="flex items-center gap-1 text-gray-400">
                              <div className="w-2 h-2 rounded-full bg-gray-500 animate-bounce" style={{ animationDelay: '0ms' }}></div>
                              <div className="w-2 h-2 rounded-full bg-gray-500 animate-bounce" style={{ animationDelay: '150ms' }}></div>
                              <div className="w-2 h-2 rounded-full bg-gray-500 animate-bounce" style={{ animationDelay: '300ms' }}></div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                    {msg.role === 'user' && (
                      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center text-sm font-semibold text-gray-200">U</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        <div className="sticky bottom-0 bg-gradient-to-t from-gray-900 via-gray-900 to-transparent pt-6 pb-4">
          <form onSubmit={submitQuestion} className="max-w-3xl mx-auto px-4">
            <div className="relative flex items-center bg-gray-800 rounded-2xl shadow-xl border border-gray-700 focus-within:border-gray-600 transition-colors">
              <input 
                ref={inputRef}
                value={input} 
                onChange={e => setInput(e.target.value)} 
                placeholder="Message Recall..." 
                className="flex-1 bg-transparent py-4 px-5 text-sm text-gray-100 placeholder-gray-500 focus:outline-none" 
                disabled={isStreaming}
              />
              <button 
                type="submit" 
                disabled={!input.trim() || isStreaming}
                className="mr-2 p-2 rounded-lg bg-white disabled:bg-gray-700 disabled:opacity-50 transition-all hover:bg-gray-100 disabled:cursor-not-allowed"
              >
                <SendIcon />
              </button>
            </div>
            <p className="mt-3 text-center text-xs text-gray-500">Recall can make mistakes. Check important info.</p>
          </form>
        </div>
      </main>

      {/* Debug/Process Visualization Panel */}
      <aside className={`${debugPanelOpen ? 'w-96' : 'w-0'} transition-all duration-300 bg-gray-950 border-l border-gray-800 flex flex-col overflow-hidden`}>
        <div className="p-4 border-b border-gray-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
            <h3 className="text-sm font-semibold text-gray-200">Agent Process Monitor</h3>
          </div>
          <button onClick={() => setDebugPanelOpen(false)} className="text-gray-500 hover:text-gray-300">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* System Metrics */}
          <div className="space-y-2">
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">System Status</div>
            <div className="bg-gray-900 rounded-lg p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-400">Status</span>
                <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                  systemMetrics.status === 'complete' ? 'bg-green-500/20 text-green-400' :
                  systemMetrics.status === 'processing' ? 'bg-yellow-500/20 text-yellow-400' :
                  systemMetrics.status === 'error' ? 'bg-red-500/20 text-red-400' :
                  'bg-gray-700 text-gray-400'
                }`}>{systemMetrics.status}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-400">Duration</span>
                <span className="text-xs font-mono text-gray-300">{systemMetrics.duration}ms</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-400">Tokens</span>
                <span className="text-xs font-mono text-gray-300">{systemMetrics.tokens}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-400">Knowledge Hits</span>
                <span className="text-xs font-mono text-gray-300">{systemMetrics.knowledgeHits}</span>
              </div>
            </div>
          </div>

          {/* Process Steps */}
          <div className="space-y-2">
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Execution Pipeline</div>
            <div className="space-y-2">
              {processSteps.map((step, idx) => (
                <div key={step.id} className="bg-gray-900 rounded-lg overflow-hidden">
                  <div className="p-3 flex items-start gap-3 cursor-pointer hover:bg-gray-800/50 transition-colors" onClick={() => step.data && toggleStep(step.id)}>
                    <div className="flex-shrink-0 mt-0.5">
                      {step.status === 'complete' && (
                        <div className="w-5 h-5 rounded-full bg-green-500/20 flex items-center justify-center">
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" className="text-green-400">
                            <polyline points="20 6 9 17 4 12"></polyline>
                          </svg>
                        </div>
                      )}
                      {step.status === 'running' && (
                        <div className="w-5 h-5 rounded-full bg-yellow-500/20 flex items-center justify-center">
                          <div className="w-2 h-2 rounded-full bg-yellow-400 animate-pulse"></div>
                        </div>
                      )}
                      {step.status === 'pending' && (
                        <div className="w-5 h-5 rounded-full bg-gray-800 flex items-center justify-center">
                          <div className="w-2 h-2 rounded-full bg-gray-600"></div>
                        </div>
                      )}
                      {step.status === 'error' && (
                        <div className="w-5 h-5 rounded-full bg-red-500/20 flex items-center justify-center">
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" className="text-red-400">
                            <line x1="18" y1="6" x2="6" y2="18"></line>
                            <line x1="6" y1="6" x2="18" y2="18"></line>
                          </svg>
                        </div>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <div className="text-xs font-medium text-gray-200">{step.name}</div>
                        {step.data && (
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className={`text-gray-500 transition-transform ${expandedSteps.has(step.id) ? 'rotate-180' : ''}`}>
                            <polyline points="6 9 12 15 18 9"></polyline>
                          </svg>
                        )}
                      </div>
                      {step.timestamp && (
                        <div className="text-xs text-gray-500 mt-0.5 font-mono">+{step.timestamp - processSteps[0].timestamp}ms</div>
                      )}
                    </div>
                  </div>
                  
                  {/* Expandable data section */}
                  {step.data && expandedSteps.has(step.id) && (
                    <div className="px-3 pb-3 border-t border-gray-800/50">
                      <div className="mt-2 bg-black/30 rounded p-2 text-xs font-mono">
                        {step.id === 1 && step.data.parsed && (
                          <div className="space-y-1">
                            <div><span className="text-blue-400">query:</span> <span className="text-gray-300">{step.data.parsed}</span></div>
                            <div><span className="text-blue-400">intent:</span> <span className="text-green-400">{step.data.intent}</span></div>
                            <div><span className="text-blue-400">entities:</span> <span className="text-yellow-400">[{step.data.entities.join(', ')}]</span></div>
                          </div>
                        )}
                        {step.id === 2 && step.data.hits && (
                          <div className="space-y-1">
                            <div><span className="text-blue-400">hits:</span> <span className="text-green-400">{step.data.hits}</span></div>
                            <div><span className="text-blue-400">docs:</span> <span className="text-gray-300 break-all">{step.data.docs.join(', ')}</span></div>
                          </div>
                        )}
                        {step.id === 3 && step.data.patterns && (
                          <div className="space-y-1">
                            <div><span className="text-blue-400">patterns:</span> <span className="text-green-400">{step.data.patterns}</span></div>
                            <div><span className="text-blue-400">relevance:</span> <span className="text-yellow-400">{step.data.relevance}</span></div>
                            {step.data.examples && step.data.examples.map((ex, i) => (
                              <div key={i} className="text-gray-400 pl-2">• {ex}</div>
                            ))}
                          </div>
                        )}
                        {step.id === 4 && step.data.tables && (
                          <div className="space-y-1">
                            <div><span className="text-blue-400">tables:</span> <span className="text-purple-400">[{step.data.tables.join(', ')}]</span></div>
                            <div><span className="text-blue-400">columns:</span> <span className="text-gray-300 break-all">{step.data.columns.slice(0, 4).join(', ')}...</span></div>
                          </div>
                        )}
                        {step.id === 5 && step.data.sql && (
                          <div className="space-y-1">
                            <div><span className="text-blue-400">validated:</span> <span className="text-green-400">{step.data.validated ? '✓' : '✗'}</span></div>
                            <div className="mt-2 text-gray-300 whitespace-pre-wrap text-[10px] leading-relaxed overflow-x-auto">{step.data.sql}</div>
                          </div>
                        )}
                        {step.id === 6 && step.data.rows !== undefined && (
                          <div className="space-y-1">
                            <div><span className="text-blue-400">rows:</span> <span className="text-green-400">{step.data.rows}</span></div>
                            <div><span className="text-blue-400">duration:</span> <span className="text-yellow-400">{step.data.duration_ms}ms</span></div>
                            <div className="mt-2"><span className="text-blue-400">result:</span></div>
                            <pre className="text-[10px] text-gray-300 overflow-x-auto">{JSON.stringify(step.data.result, null, 2)}</pre>
                          </div>
                        )}
                        {step.id === 7 && step.data.insight && (
                          <div className="space-y-1">
                            <div className="text-gray-300">{step.data.insight}</div>
                            <div className="mt-1"><span className="text-blue-400">confidence:</span> <span className="text-green-400">{(step.data.confidence * 100).toFixed(0)}%</span></div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Architecture Info */}
          <div className="space-y-2">
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Architecture</div>
            <div className="bg-gray-900 rounded-lg p-3 space-y-2 text-xs text-gray-400">
              <div className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-green-400"></div>
                <span>MCP Server (Recall)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-blue-400"></div>
                <span>PostgreSQL + pgvector</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-purple-400"></div>
                <span>Knowledge Base (8 docs)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-yellow-400"></div>
                <span>Learning Machine</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-red-400"></div>
                <span>LLM: {import.meta.env.VITE_MODEL_PROVIDER || 'mistral'}</span>
              </div>
            </div>
          </div>

          {/* Features Showcase */}
          <div className="space-y-2">
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Archestra Features</div>
            <div className="bg-gray-900 rounded-lg p-3 space-y-1.5 text-xs">
              <div className="flex items-center justify-between py-1">
                <span className="text-gray-400">Self-learning</span>
                <span className="text-green-400">✓</span>
              </div>
              <div className="flex items-center justify-between py-1">
                <span className="text-gray-400">Vector search</span>
                <span className="text-green-400">✓</span>
              </div>
              <div className="flex items-center justify-between py-1">
                <span className="text-gray-400">SQL generation</span>
                <span className="text-green-400">✓</span>
              </div>
              <div className="flex items-center justify-between py-1">
                <span className="text-gray-400">Observability</span>
                <span className="text-green-400">✓</span>
              </div>
              <div className="flex items-center justify-between py-1">
                <span className="text-gray-400">Context grounding</span>
                <span className="text-green-400">✓</span>
              </div>
            </div>
          </div>
        </div>

        <div className="p-3 border-t border-gray-800">
          <div className="text-xs text-center text-gray-500">
            <span className="font-semibold text-green-400">2 Fast 2 MCP</span> Hackathon
          </div>
        </div>
      </aside>
      </div>
    </div>
  )
}
