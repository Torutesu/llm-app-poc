'use client'

import { useState, useRef, useEffect } from 'react'
import { Send, Bot, User, FileText, Loader2 } from 'lucide-react'
import { chatAPI } from '@/lib/api'
import type { ChatMessage } from '@/types'

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || loading) return

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date().toISOString(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      const response = await chatAPI.ask(input, true)

      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.response || response.answer || '回答を生成できませんでした。',
        timestamp: new Date().toISOString(),
        contextDocs: response.context_docs || [],
      }

      setMessages((prev) => [...prev, assistantMessage])
    } catch (error) {
      console.error('Error asking question:', error)
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'エラーが発生しました。もう一度お試しください。',
        timestamp: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-8 py-4">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">AI チャット</h1>
        <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
          ドキュメントについて質問してください
        </p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-8 space-y-6">
        {messages.length === 0 && (
          <div className="text-center py-12">
            <Bot className="h-16 w-16 text-gray-400 mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
              何かお手伝いできることはありますか？
            </h2>
            <p className="text-gray-600 dark:text-gray-400">
              ドキュメントについて質問してください
            </p>
            <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-4 max-w-2xl mx-auto">
              <SuggestionCard
                title="売上データを分析"
                description="Q4の売上推移について教えてください"
                onClick={() => setInput('Q4の売上推移について教えてください')}
              />
              <SuggestionCard
                title="製品ロードマップ"
                description="2025年の製品計画は？"
                onClick={() => setInput('2025年の製品計画について教えてください')}
              />
              <SuggestionCard
                title="会議議事録"
                description="先週の会議の要約を教えて"
                onClick={() => setInput('先週の会議の主な決定事項を教えてください')}
              />
              <SuggestionCard
                title="技術ドキュメント"
                description="APIの使い方を教えて"
                onClick={() => setInput('APIの認証方法について教えてください')}
              />
            </div>
          </div>
        )}

        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}

        {loading && (
          <div className="flex items-start space-x-3">
            <div className="flex-shrink-0 w-10 h-10 rounded-full bg-blue-100 dark:bg-blue-900 flex items-center justify-center">
              <Bot className="h-6 w-6 text-blue-600 dark:text-blue-300" />
            </div>
            <div className="flex-1 bg-white dark:bg-gray-800 rounded-lg shadow p-4">
              <div className="flex items-center space-x-2 text-gray-600 dark:text-gray-400">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>回答を生成中...</span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 p-4">
        <form onSubmit={handleSubmit} className="max-w-4xl mx-auto">
          <div className="flex space-x-4">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="質問を入力してください..."
              className="flex-1 px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition flex items-center space-x-2"
            >
              <Send className="h-5 w-5" />
              <span>送信</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex items-start space-x-3 ${isUser ? 'flex-row-reverse space-x-reverse' : ''}`}>
      <div
        className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center ${
          isUser ? 'bg-gray-200 dark:bg-gray-700' : 'bg-blue-100 dark:bg-blue-900'
        }`}
      >
        {isUser ? (
          <User className="h-6 w-6 text-gray-600 dark:text-gray-300" />
        ) : (
          <Bot className="h-6 w-6 text-blue-600 dark:text-blue-300" />
        )}
      </div>
      <div className={`flex-1 ${isUser ? 'flex justify-end' : ''}`}>
        <div
          className={`inline-block max-w-3xl p-4 rounded-lg shadow ${
            isUser
              ? 'bg-blue-600 text-white'
              : 'bg-white dark:bg-gray-800 text-gray-900 dark:text-white'
          }`}
        >
          <p className="whitespace-pre-wrap">{message.content}</p>

          {message.contextDocs && message.contextDocs.length > 0 && (
            <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
              <div className="text-sm font-medium mb-2 flex items-center space-x-2">
                <FileText className="h-4 w-4" />
                <span>参照元ドキュメント ({message.contextDocs.length})</span>
              </div>
              <div className="space-y-2">
                {message.contextDocs.slice(0, 3).map((doc, idx) => (
                  <div
                    key={idx}
                    className="text-xs p-2 bg-gray-50 dark:bg-gray-700 rounded border border-gray-200 dark:border-gray-600"
                  >
                    <div className="font-medium text-blue-600 dark:text-blue-400 mb-1">
                      {doc.metadata.path.split('/').pop()}
                    </div>
                    <div className="text-gray-600 dark:text-gray-300 line-clamp-2">
                      {doc.text}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
        <div className={`text-xs text-gray-500 dark:text-gray-400 mt-1 ${isUser ? 'text-right' : ''}`}>
          {new Date(message.timestamp).toLocaleTimeString('ja-JP')}
        </div>
      </div>
    </div>
  )
}

function SuggestionCard({
  title,
  description,
  onClick,
}: {
  title: string
  description: string
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className="text-left p-4 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-blue-500 dark:hover:border-blue-500 transition"
    >
      <h3 className="font-semibold text-gray-900 dark:text-white mb-1">{title}</h3>
      <p className="text-sm text-gray-600 dark:text-gray-400">{description}</p>
    </button>
  )
}
