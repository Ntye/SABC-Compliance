import { useEffect, useRef, useState } from 'react'
import { Bot, ChevronDown, Loader2, Send, X } from 'lucide-react'
import { assistantChat, assistantHealth } from '../../lib/api.js'
import { useT } from '../../context/LangContext.jsx'

function Message({ msg }) {
  const isUser = msg.role === 'user'
  return (
    <div className={`flex gap-2 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      {!isUser && (
        <div className="w-6 h-6 rounded-full bg-brand/20 flex items-center justify-center flex-shrink-0 mt-0.5">
          <Bot size={12} className="text-brand" />
        </div>
      )}
      <div
        className={[
          'max-w-[80%] px-3 py-2 rounded-2xl text-[12px] leading-relaxed whitespace-pre-wrap',
          isUser
            ? 'bg-brand text-white rounded-tr-none'
            : 'bg-gray-100 text-gray-800 rounded-tl-none',
        ].join(' ')}
      >
        {msg.content}
      </div>
    </div>
  )
}

export default function ChatWidget() {
  const t = useT()
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [available, setAvailable] = useState(null) // null=unchecked, true/false
  const bottomRef = useRef(null)

  // Check Ollama availability once on mount
  useEffect(() => {
    assistantHealth()
      .then((d) => setAvailable(d?.status === 'up'))
      .catch(() => setAvailable(false))
  }, [])

  // Scroll to bottom on new messages
  useEffect(() => {
    if (open) bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, open])

  async function sendMessage() {
    const text = input.trim()
    if (!text || loading) return
    const newMsg = { role: 'user', content: text }
    const updated = [...messages, newMsg]
    setMessages(updated)
    setInput('')
    setLoading(true)
    try {
      const res = await assistantChat(
        updated.map((m) => ({ role: m.role, content: m.content })),
      )
      setMessages((prev) => [...prev, { role: 'assistant', content: res.reply }])
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `⚠️ ${err.message || t('chat.error')}` },
      ])
    } finally {
      setLoading(false)
    }
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col items-end gap-2">
      {/* Chat panel */}
      {open && (
        <div className="w-80 sm:w-96 bg-white rounded-2xl shadow-2xl border border-gray-200 flex flex-col overflow-hidden"
          style={{ height: '480px' }}>
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 bg-brand text-white">
            <div className="flex items-center gap-2">
              <Bot size={16} />
              <span className="text-[13px] font-semibold">{t('chat.title')}</span>
            </div>
            <div className="flex items-center gap-2">
              {available === false && (
                <span className="text-[10px] bg-white/20 px-1.5 py-0.5 rounded">
                  {t('chat.offline')}
                </span>
              )}
              <button onClick={() => setOpen(false)} className="opacity-80 hover:opacity-100">
                <ChevronDown size={16} />
              </button>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-3 space-y-3">
            {messages.length === 0 && (
              <div className="text-center pt-8 space-y-2">
                <Bot size={32} className="mx-auto text-gray-300" />
                <p className="text-[12px] text-gray-400">{t('chat.placeholder')}</p>
                {available === false && (
                  <p className="text-[11px] text-amber-600 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mx-2">
                    {t('chat.notRunning')}
                  </p>
                )}
              </div>
            )}
            {messages.map((m, i) => <Message key={i} msg={m} />)}
            {loading && (
              <div className="flex gap-2">
                <div className="w-6 h-6 rounded-full bg-brand/20 flex items-center justify-center flex-shrink-0">
                  <Bot size={12} className="text-brand" />
                </div>
                <div className="bg-gray-100 rounded-2xl rounded-tl-none px-3 py-2">
                  <Loader2 size={14} className="text-gray-400 animate-spin" />
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="px-3 py-2 border-t border-gray-100 flex items-end gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder={t('chat.inputPlaceholder')}
              rows={1}
              className="flex-1 text-[12px] resize-none outline-none text-gray-700 placeholder-gray-400 max-h-24 overflow-y-auto py-1"
            />
            <button
              onClick={sendMessage}
              disabled={!input.trim() || loading}
              className="p-1.5 rounded-lg bg-brand text-white disabled:opacity-40 hover:bg-brand/90 transition-colors flex-shrink-0"
            >
              <Send size={14} />
            </button>
          </div>
        </div>
      )}

      {/* Floating button */}
      <button
        onClick={() => setOpen((v) => !v)}
        className={[
          'w-12 h-12 rounded-full shadow-lg flex items-center justify-center transition-all',
          open ? 'bg-gray-600 hover:bg-gray-700' : 'bg-brand hover:bg-brand/90',
        ].join(' ')}
        title={t('chat.title')}
      >
        {open ? <X size={20} className="text-white" /> : <Bot size={22} className="text-white" />}
      </button>
    </div>
  )
}
