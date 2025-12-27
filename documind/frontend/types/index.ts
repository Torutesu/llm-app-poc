// API Types
export interface Document {
  id: string
  path: string
  name: string
  size: number
  type: string
  uploadedAt: string
  indexedAt?: string
  status: 'uploading' | 'processing' | 'indexed' | 'error'
  metadata?: Record<string, any>
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  contextDocs?: ContextDocument[]
}

export interface ContextDocument {
  text: string
  metadata: {
    path: string
    page?: number
    [key: string]: any
  }
}

export interface RAGConfig {
  llm_model: string
  embedding_model: string
  search_topk: number
  temperature: number
  max_tokens: number
}

export interface User {
  id: string
  email: string
  name: string
  role: 'admin' | 'member' | 'viewer'
  organizationId: string
}

export interface Organization {
  id: string
  name: string
  plan: 'free' | 'pro' | 'enterprise'
  members: number
  documentsCount: number
  storageUsed: number
  storageLimit: number
}

export interface DataSource {
  id: string
  type: 'local' | 'gdrive' | 'sharepoint' | 's3'
  name: string
  config: Record<string, any>
  status: 'active' | 'error' | 'paused'
  lastSync?: string
}
