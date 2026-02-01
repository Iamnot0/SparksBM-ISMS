interface SessionResponse {
  sessionId: string
}

interface ChatResponse {
  status: string
  result?: string | {
    type: 'table' | 'object_detail'
    title?: string
    columns?: string[]
    data?: any[]
    total?: number
    shown?: number
    [key: string]: any
  }
  type?: string
  dataType?: 'table' | 'object_detail'
  error?: string
}

export const useApi = () => {
  const config = useRuntimeConfig()
  const apiBase = config.public.apiBase as string

  const createSession = async (userId: string = 'default'): Promise<SessionResponse> => {
    try {
      const response = await $fetch<SessionResponse>(`${apiBase}/api/agent/session`, {
        method: 'POST',
        params: { userId }
      })
      return response
    } catch (error) {
      console.error('Failed to create session:', error)
      throw error
    }
  }

  const sendChat = async (message: string, sessionId: string, sources: any[] = []): Promise<ChatResponse> => {
    try {
      const response = await $fetch<ChatResponse>(`${apiBase}/api/agent/chat`, {
        method: 'POST',
        body: {
          message,
          sessionId,
          sources
        }
      })
      return response
    } catch (error) {
      console.error('Failed to send chat:', error)
      throw error
    }
  }

  const addContext = async (sessionId: string, sources: any[]): Promise<any> => {
    try {
      const response = await $fetch(`${apiBase}/api/agent/context`, {
        method: 'POST',
        body: {
          sessionId,
          sources
        }
      })
      return response
    } catch (error) {
      console.error('Failed to add context:', error)
      throw error
    }
  }

  return {
    createSession,
    sendChat,
    addContext
  }
}
