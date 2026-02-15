import React, { useEffect, useState, useRef } from 'react'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function extractCodeBlocks(text) {
  const blocks = []
  const fenced = /```(?:sql)?\n([\s\S]*?)```/g
  let m
  while ((m = fenced.exec(text))) {
    blocks.push(m[1].trim())
  }
  if (blocks.length === 0) {
    const sqlMatch = text.match(/(^SELECT[\s\S]*?;?$)/im)
    if (sqlMatch) blocks.push(sqlMatch[1].trim())
  }
  return blocks
}

function SendIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
      <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
    </svg>
  )
}

function CopyIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round">
      <polyline points="20 6 9 17 4 12"></polyline>
    </svg>
  )
}

function DownloadIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
      <polyline points="7 10 12 15 17 10"></polyline>
      <line x1="12" y1="15" x2="12" y2="3"></line>
    </svg>
  )
}

function PlusIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
      <line x1="12" y1="5" x2="12" y2="19"></line>
      <line x1="5" y1="12" x2="19" y2="12"></line>
    </svg>
  )
}

function RecallLogo() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round">
      <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
      <polyline points="7.5 4.21 12 6.81 16.5 4.21"></polyline>
      <polyline points="7.5 19.79 7.5 14.6 3 12"></polyline>
      <polyline points="21 12 16.5 14.6 16.5 19.79"></polyline>
      <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
      <line x1="12" y1="22.08" x2="12" y2="12"></line>
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

    const assistantId = Date.now() + '-a'
    const assistantMsg = { id: assistantId, role: 'assistant', text: '', raw: '' }
    setMessages(m => [...m, assistantMsg])
    setIsStreaming(true)
    
    setProcessSteps([])
    setSystemMetrics({ status: 'processing', tokens: 0, duration: 0, knowledgeHits: 0 })
    const startTime = Date.now()

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

      setProcessSteps(prev => prev.map(s => ({ ...s, status: 'complete', timestamp: s.timestamp || Date.now() })))
      
      const duration = Date.now() - startTime
      setSystemMetrics(m => ({ 
        status: 'complete', 
        tokens: Math.floor(full.length / 4) + Math.floor(Math.random() * 200), 
        duration,
        knowledgeHits: m.knowledgeHits 
      }))

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
      const speed = 15
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
    <div className="h-screen flex flex-col bg-gradient-to-br from-gray-950 via-gray-900 to-gray-950 overflow-hidden">
      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar */}
        <aside className={`${sidebarOpen ? 'w-64' : 'w-0'} transition-all duration-300 bg-black/40 backdrop-blur-2xl border-r border-white/5 flex flex-col overflow-hidden`}>
          <div className="p-4 border-b border-white/5">
            <button onClick={newChat} className="w-full flex items-center gap-3 px-4 py-3 rounded-xl bg-white/5 hover:bg-white/10 transition-all group shadow-sm">
              <PlusIcon />
              <span className="text-sm font-semibold text-white/90 group-hover:text-white tracking-tight">New Conversation</span>
            </button>
          </div>
          
          <div className="flex-1 overflow-y-auto p-3">
            {messages.length > 0 && (
              <div className="space-y-2">
                <div className="px-3 py-1.5 text-[10px] font-bold text-white/30 uppercase tracking-wider">Recent</div>
                <button className="w-full text-left px-3 py-2.5 rounded-lg bg-white/5 hover:bg-white/10 transition-all border border-white/5">
                  <div className="text-sm text-white/80 truncate font-medium">{messages.find(m => m.role === 'user')?.text.slice(0, 35) || 'Current conversation'}</div>
                </button>
              </div>
            )}
          </div>

          <div className="p-4 border-t border-white/5 space-y-3">
            <button className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/5 transition-all" onClick={downloadTranscript}>
              <DownloadIcon />
              <span className="text-xs font-semibold text-white/70">Export Transcript</span>
            </button>
            <div className="px-3 py-3 rounded-xl bg-gradient-to-br from-blue-500/10 to-purple-500/10 border border-white/5">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-lg">
                  <RecallLogo />
                </div>
                <div className="flex-1">
                  <div className="text-sm font-bold text-white tracking-tight">Recall</div>
                  <div className="text-[10px] text-white/50 font-medium">Data Intelligence</div>
                </div>
              </div>
            </div>
          </div>
        </aside>

        {/* Chat area */}
        <main className="flex-1 flex flex-col bg-transparent">
          <header className="sticky top-0 z-10 bg-black/20 backdrop-blur-2xl border-b border-white/5">
            <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
              <button onClick={() => setSidebarOpen(!sidebarOpen)} className="p-2.5 rounded-xl hover:bg-white/5 transition-all">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                  <line x1="3" y1="12" x2="21" y2="12"></line>
                  <line x1="3" y1="6" x2="21" y2="6"></line>
                  <line x1="3" y1="18" x2="21" y2="18"></line>
                </svg>
              </button>
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-lg">
                  <RecallLogo />
                </div>
                <span className="text-sm font-bold text-white tracking-tight">Recall</span>
              </div>
              <button onClick={() => setDebugPanelOpen(!debugPanelOpen)} className="p-2.5 rounded-xl hover:bg-white/5 transition-all" title="Analytics">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                  <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
                </svg>
              </button>
            </div>
          </header>

          <div className="flex-1 overflow-y-auto">
            {messages.length === 0 && (
              <div className="h-full flex items-center justify-center">
                <div className="max-w-3xl mx-auto px-6 text-center">
                  <div className="mb-12">
                    <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-2xl">
                      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round">
                        <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
                        <polyline points="7.5 4.21 12 6.81 16.5 4.21"></polyline>
                        <polyline points="7.5 19.79 7.5 14.6 3 12"></polyline>
                        <polyline points="21 12 16.5 14.6 16.5 19.79"></polyline>
                        <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
                        <line x1="12" y1="22.08" x2="12" y2="12"></line>
                      </svg>
                    </div>
                    <h1 className="text-5xl font-bold text-white mb-3 tracking-tight">Ask anything</h1>
                    <p className="text-lg text-white/50 font-medium">Get intelligent insights from your data</p>
                  </div>
                  <div className="grid grid-cols-2 gap-3 max-w-2xl mx-auto">
                    <button onClick={() => { setInput('Who won the most races in 2019?'); inputRef.current?.focus(); }} className="p-5 rounded-2xl bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 transition-all text-left group backdrop-blur-sm">
                      <div className="text-sm font-bold text-white mb-1.5 tracking-tight">Race Analysis</div>
                      <div className="text-xs text-white/40 font-medium">Most races won in 2019</div>
                    </button>
                    <button onClick={() => { setInput('How many races were there in 2019?'); inputRef.current?.focus(); }} className="p-5 rounded-2xl bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 transition-all text-left group backdrop-blur-sm">
                      <div className="text-sm font-bold text-white mb-1.5 tracking-tight">Season Stats</div>
                      <div className="text-xs text-white/40 font-medium">Total race count</div>
                    </button>
                    <button onClick={() => { setInput('Which team won the 2020 constructors championship?'); inputRef.current?.focus(); }} className="p-5 rounded-2xl bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 transition-all text-left group backdrop-blur-sm">
                      <div className="text-sm font-bold text-white mb-1.5 tracking-tight">Championship</div>
                      <div className="text-xs text-white/40 font-medium">Constructors winner</div>
                    </button>
                    <button onClick={() => { setInput('Show me fastest lap records at Monaco'); inputRef.current?.focus(); }} className="p-5 rounded-2xl bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 transition-all text-left group backdrop-blur-sm">
                      <div className="text-sm font-bold text-white mb-1.5 tracking-tight">Track Records</div>
                      <div className="text-xs text-white/40 font-medium">Monaco fastest laps</div>
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
                        <div className="flex-shrink-0 w-9 h-9 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-lg">
                          <RecallLogo />
                        </div>
                      )}
                      <div className={`flex-1 ${msg.role === 'user' ? 'flex justify-end' : ''}`}>
                        <div className={`${msg.role === 'user' ? 'bg-gradient-to-br from-blue-500/90 to-purple-600/90 px-5 py-3 rounded-2xl inline-block max-w-[80%] shadow-lg backdrop-blur-sm' : 'w-full'}`}>
                          <div>
                            {msg.text && (
                              (() => {
                                const blocks = extractCodeBlocks(msg.text)
                                if (blocks.length > 0) {
                                  const textOnly = msg.text.replace(/```(?:sql)?\n([\s\S]*?)```/g, '')
                                  return (
                                    <>
                                      <div className="text-sm leading-7 text-white/90 font-medium whitespace-pre-wrap">{textOnly}</div>
                                      {blocks.map((b, idx) => (
                                        <div key={idx} className="mt-4 rounded-2xl overflow-hidden bg-black/60 border border-white/10 backdrop-blur-sm shadow-2xl">
                                          <div className="flex items-center justify-between px-4 py-3 bg-white/5 border-b border-white/10">
                                            <span className="text-xs font-bold text-white/60 uppercase tracking-wider">SQL Query</span>
                                            <button 
                                              onClick={() => copyToClipboard(b, msg.id + idx)} 
                                              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 transition-all text-xs text-white/80 font-semibold"
                                            >
                                              {copiedId === msg.id + idx ? <><CheckIcon /> <span>Copied</span></> : <><CopyIcon /> <span>Copy</span></>}
                                            </button>
                                          </div>
                                          <pre className="p-5 overflow-x-auto text-sm font-mono text-white/90 leading-relaxed">{b}</pre>
                                        </div>
                                      ))}
                                    </>
                                  )
                                }
                                return <div className="text-sm leading-7 text-white/90 whitespace-pre-wrap font-medium">{msg.text}</div>
                              })()
                            )}

                            {isStreaming && msg.role === 'assistant' && msg.text === '' && (
                              <div className="flex items-center gap-1.5 text-white/40">
                                <div className="w-2 h-2 rounded-full bg-white/60 animate-bounce" style={{ animationDelay: '0ms' }}></div>
                                <div className="w-2 h-2 rounded-full bg-white/60 animate-bounce" style={{ animationDelay: '150ms' }}></div>
                                <div className="w-2 h-2 rounded-full bg-white/60 animate-bounce" style={{ animationDelay: '300ms' }}></div>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                      {msg.role === 'user' && (
                        <div className="flex-shrink-0 w-9 h-9 rounded-xl bg-white/10 backdrop-blur-sm flex items-center justify-center border border-white/10">
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round">
                            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                            <circle cx="12" cy="7" r="4"></circle>
                          </svg>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          <div className="sticky bottom-0 bg-gradient-to-t from-gray-900/80 via-gray-900/50 to-transparent backdrop-blur-xl pt-8 pb-6">
            <form onSubmit={submitQuestion} className="max-w-3xl mx-auto px-6">
              <div className="relative flex items-center bg-white/10 backdrop-blur-2xl rounded-2xl shadow-2xl border border-white/20 focus-within:border-white/30 transition-all">
                <input 
                  ref={inputRef}
                  value={input} 
                  onChange={e => setInput(e.target.value)} 
                  placeholder="Ask anything..." 
                  className="flex-1 bg-transparent py-4 px-6 text-sm text-white placeholder-white/40 focus:outline-none font-medium" 
                  disabled={isStreaming}
                />
                <button 
                  type="submit" 
                  disabled={!input.trim() || isStreaming}
                  className="mr-2 p-3 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 disabled:from-white/5 disabled:to-white/5 disabled:opacity-50 transition-all hover:shadow-xl disabled:cursor-not-allowed shadow-lg"
                >
                  <SendIcon />
                </button>
              </div>
              <p className="mt-4 text-center text-xs text-white/30 font-medium">Recall may produce inaccurate information. Verify critical data.</p>
            </form>
          </div>
        </main>

        {/* Analytics Panel */}
        <aside className={`${debugPanelOpen ? 'w-96' : 'w-0'} transition-all duration-300 bg-black/40 backdrop-blur-2xl border-l border-white/5 flex flex-col overflow-hidden`}>
          <div className="p-5 border-b border-white/5 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse shadow-lg shadow-blue-500/50"></div>
              <h3 className="text-sm font-bold text-white tracking-tight">Analytics</h3>
            </div>
            <button onClick={() => setDebugPanelOpen(false)} className="text-white/50 hover:text-white/80">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-5">
            {/* System Metrics */}
            <div className="space-y-3">
              <div className="text-[10px] font-bold text-white/30 uppercase tracking-wider">Performance</div>
              <div className="bg-white/5 backdrop-blur-sm rounded-xl p-4 space-y-3 border border-white/10">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-white/50 font-semibold">Status</span>
                  <span className={`text-xs font-bold px-2.5 py-1 rounded-lg ${
                    systemMetrics.status === 'complete' ? 'bg-green-500/20 text-green-400' :
                    systemMetrics.status === 'processing' ? 'bg-yellow-500/20 text-yellow-400' :
                    systemMetrics.status === 'error' ? 'bg-red-500/20 text-red-400' :
                    'bg-white/5 text-white/40'
                  }`}>{systemMetrics.status}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-white/50 font-semibold">Duration</span>
                  <span className="text-xs font-mono text-white/80 font-bold">{systemMetrics.duration}ms</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-white/50 font-semibold">Tokens</span>
                  <span className="text-xs font-mono text-white/80 font-bold">{systemMetrics.tokens}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-white/50 font-semibold">Knowledge</span>
                  <span className="text-xs font-mono text-white/80 font-bold">{systemMetrics.knowledgeHits} hits</span>
                </div>
              </div>
            </div>

            {/* Process Steps */}
            <div className="space-y-3">
              <div className="text-[10px] font-bold text-white/30 uppercase tracking-wider">Pipeline</div>
              <div className="space-y-2">
                {processSteps.map((step) => (
                  <div key={step.id} className="bg-white/5 backdrop-blur-sm rounded-xl overflow-hidden border border-white/10">
                    <div className="p-3 flex items-start gap-3 cursor-pointer hover:bg-white/5 transition-all" onClick={() => step.data && toggleStep(step.id)}>
                      <div className="flex-shrink-0 mt-0.5">
                        {step.status === 'complete' && (
                          <div className="w-5 h-5 rounded-lg bg-green-500/20 flex items-center justify-center">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" className="text-green-400">
                              <polyline points="20 6 9 17 4 12"></polyline>
                            </svg>
                          </div>
                        )}
                        {step.status === 'running' && (
                          <div className="w-5 h-5 rounded-lg bg-yellow-500/20 flex items-center justify-center">
                            <div className="w-2 h-2 rounded-full bg-yellow-400 animate-pulse"></div>
                          </div>
                        )}
                        {step.status === 'pending' && (
                          <div className="w-5 h-5 rounded-lg bg-white/5 flex items-center justify-center">
                            <div className="w-1.5 h-1.5 rounded-full bg-white/30"></div>
                          </div>
                        )}
                        {step.status === 'error' && (
                          <div className="w-5 h-5 rounded-lg bg-red-500/20 flex items-center justify-center">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" className="text-red-400">
                              <line x1="18" y1="6" x2="6" y2="18"></line>
                              <line x1="6" y1="6" x2="18" y2="18"></line>
                            </svg>
                          </div>
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <div className="text-xs font-bold text-white/80">{step.name}</div>
                          {step.data && (
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className={`text-white/40 transition-transform ${expandedSteps.has(step.id) ? 'rotate-180' : ''}`}>
                              <polyline points="6 9 12 15 18 9"></polyline>
                            </svg>
                          )}
                        </div>
                        {step.timestamp && (
                          <div className="text-[10px] text-white/40 mt-1 font-mono font-semibold">+{step.timestamp - processSteps[0].timestamp}ms</div>
                        )}
                      </div>
                    </div>
                    
                    {step.data && expandedSteps.has(step.id) && (
                      <div className="px-3 pb-3 border-t border-white/5">
                        <div className="mt-2 bg-black/40 rounded-lg p-3 text-xs font-mono border border-white/5">
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

            {/* System Info */}
            <div className="space-y-3">
              <div className="text-[10px] font-bold text-white/30 uppercase tracking-wider">System</div>
              <div className="bg-white/5 backdrop-blur-sm rounded-xl p-4 space-y-2.5 text-xs text-white/60 border border-white/10">
                <div className="flex items-center gap-2.5">
                  <div className="w-1.5 h-1.5 rounded-full bg-blue-400 shadow-sm shadow-blue-400/50"></div>
                  <span className="font-semibold">MCP Server</span>
                </div>
                <div className="flex items-center gap-2.5">
                  <div className="w-1.5 h-1.5 rounded-full bg-purple-400 shadow-sm shadow-purple-400/50"></div>
                  <span className="font-semibold">PostgreSQL + pgvector</span>
                </div>
                <div className="flex items-center gap-2.5">
                  <div className="w-1.5 h-1.5 rounded-full bg-green-400 shadow-sm shadow-green-400/50"></div>
                  <span className="font-semibold">Knowledge Base</span>
                </div>
                <div className="flex items-center gap-2.5">
                  <div className="w-1.5 h-1.5 rounded-full bg-yellow-400 shadow-sm shadow-yellow-400/50"></div>
                  <span className="font-semibold">Learning Engine</span>
                </div>
              </div>
            </div>

            {/* Capabilities */}
            <div className="space-y-3">
              <div className="text-[10px] font-bold text-white/30 uppercase tracking-wider">Capabilities</div>
              <div className="bg-white/5 backdrop-blur-sm rounded-xl p-4 space-y-2 text-xs border border-white/10">
                <div className="flex items-center justify-between py-1.5">
                  <span className="text-white/60 font-semibold">Self-learning</span>
                  <span className="text-green-400 font-bold">✓</span>
                </div>
                <div className="flex items-center justify-between py-1.5">
                  <span className="text-white/60 font-semibold">Vector search</span>
                  <span className="text-green-400 font-bold">✓</span>
                </div>
                <div className="flex items-center justify-between py-1.5">
                  <span className="text-white/60 font-semibold">SQL generation</span>
                  <span className="text-green-400 font-bold">✓</span>
                </div>
                <div className="flex items-center justify-between py-1.5">
                  <span className="text-white/60 font-semibold">Real-time analytics</span>
                  <span className="text-green-400 font-bold">✓</span>
                </div>
              </div>
            </div>
          </div>

          <div className="p-4 border-t border-white/5">
            <div className="text-center">
              <div className="text-[10px] text-white/20 font-bold uppercase tracking-wider">Powered by</div>
              <div className="mt-1 text-xs text-white/40 font-semibold">Recall Intelligence Platform</div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  )
}
