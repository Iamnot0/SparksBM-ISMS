<template>
  <v-app>
    <div class="notebook-layout">
    <!-- Header -->
    <div class="notebook-header">
      <div class="header-left">
        <LayoutAppLogoDesktop style="height: 32px; margin-right: 12px" />
      </div>
      <div class="header-right">
        <v-avatar size="32" color="primary">
          <span class="text-white">Mr</span>
        </v-avatar>
      </div>
    </div>

    <!-- Three-Panel Layout -->
    <div class="panel-container">
      <!-- Left Panel: Sources -->
      <div 
        class="panel panel-left" 
        :class="{ 'collapsed': leftCollapsed }"
        :style="{ width: leftCollapsed ? '60px' : leftPanelWidth + 'px' }"
      >
        <div v-if="!leftCollapsed">
          <div class="panel-header">
            <span class="panel-title">Sources</span>
            <div class="panel-toggle-icon" @click="leftCollapsed = true">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <rect x="2" y="2" width="12" height="12" stroke="currentColor" stroke-width="1" fill="none" rx="1"/>
                <line x1="4" y1="8" x2="12" y2="8" stroke="currentColor" stroke-width="1"/>
              </svg>
            </div>
          </div>
          
        </div>
        <div v-else class="panel-collapsed-content">
          <v-btn icon variant="text" @click="leftCollapsed = false">
            <v-icon>mdi-menu</v-icon>
          </v-btn>
        </div>
      </div>

      <!-- Left Divider (draggable) -->
      <div 
        v-if="!leftCollapsed"
        class="panel-divider"
        @mousedown="startResize('left')"
      ></div>

      <!-- Center Panel: Chat -->
      <div class="panel panel-center">
        <div class="panel-header">
          <span class="panel-title">Chat</span>
        </div>

        <div class="chat-content" ref="chatContentRef">
          <div v-if="chatHistory.length === 0" class="empty-chat">
            <h3>Start chatting with SparksBM Agent</h3>
            <p class="text-caption">Ask questions about ISMS operations or chat with the agent</p>
          </div>
          
          <div v-else class="messages">
            <div 
              v-for="msg in chatHistory" 
              :key="msg.id" 
              class="message"
              :class="msg.role"
            >
              <span v-if="msg.role === 'assistant'" class="agent-label">Agent:</span>
              <div v-if="msg.isTable" class="table-container">
                <table class="data-table">
                  <thead>
                    <tr>
                      <th v-for="col in msg.tableColumns" :key="col">{{ col }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(row, rowIdx) in msg.tableData" :key="`row-${rowIdx}-${JSON.stringify(row).slice(0, 50)}`">
                      <td v-for="col in msg.tableColumns" :key="`${rowIdx}-${col}`">
                        {{ row[col.toLowerCase()] || row[col] || '—' }}
                      </td>
                    </tr>
                  </tbody>
                </table>
                <div v-if="msg.tableTotal && msg.tableData && msg.tableTotal > msg.tableData.length" class="table-footer">
                  ... and {{ msg.tableTotal - msg.tableData.length }} more
                </div>
              </div>
              <div v-else class="message-text" v-html="formatMessage(msg.content)"></div>
            </div>
          </div>
        </div>

        <div class="chat-input-container">
          <div class="chat-input-row">
          <v-text-field
            v-model="currentMessage"
              :placeholder="chatInputPlaceholder"
            variant="outlined"
            density="compact"
            hide-details
            @keyup.enter="sendMessage"
              class="chat-input-field"
            />
            
            <v-btn 
              icon 
              @click="sendMessage"
              :disabled="!currentMessage.trim()"
              title="Send message"
            >
            <v-icon>mdi-send</v-icon>
          </v-btn>
          </div>
        </div>
      </div>

      <!-- Right Divider (draggable) -->
      <div 
        v-if="!rightCollapsed"
        class="panel-divider"
        @mousedown="startResize('right')"
      ></div>

      <!-- Right Panel: Studio -->
      <div 
        class="panel panel-right"
        :class="{ 'collapsed': rightCollapsed }"
        :style="{ width: rightCollapsed ? '60px' : rightPanelWidth + 'px' }"
      >
        <div v-if="!rightCollapsed" class="panel-right-content">
          <div class="panel-header">
            <span class="panel-title">Studio</span>
            <div class="panel-toggle-icon" @click="rightCollapsed = true">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <rect x="2" y="2" width="12" height="12" stroke="currentColor" stroke-width="1" fill="none" rx="1"/>
                <line x1="4" y1="8" x2="12" y2="8" stroke="currentColor" stroke-width="1"/>
              </svg>
            </div>
          </div>


          <!-- Agent Processing Menu -->
          <div class="studio-section">
            <div class="menu-category">
              <div class="category-title clickable" @click="collapsedCategories.agentProcessing = !collapsedCategories.agentProcessing">
                <v-icon size="16" class="mr-1">{{ collapsedCategories.agentProcessing ? 'mdi-chevron-right' : 'mdi-chevron-down' }}</v-icon>
                <v-icon size="16" class="mr-1">mdi-robot</v-icon>
                AGENT PROCESSING
                </div>
              <div v-show="!collapsedCategories.agentProcessing" class="isms-menu">
                

                <!-- Reasoning Steps Section -->
                <div class="reasoning-section">
                  <div class="subsection-title clickable" @click="collapsedCategories.reasoningSteps = !collapsedCategories.reasoningSteps">
                    <v-icon size="14" class="mr-1">{{ collapsedCategories.reasoningSteps ? 'mdi-chevron-right' : 'mdi-chevron-down' }}</v-icon>
                    <v-icon size="14" class="mr-1">mdi-thought-bubble</v-icon>
                    Reasoning Steps
                    <v-chip v-if="reasoningSteps.length > 0" size="x-small" color="primary" class="ml-2">{{ reasoningSteps.length }}</v-chip>
                </div>
                  <div v-show="!collapsedCategories.reasoningSteps">
                    <div v-if="reasoningSteps.length === 0" class="no-steps">
                      <span class="text-grey">No active processing</span>
                  </div>
                    <div v-else class="reasoning-steps-list">
                      <div v-for="(step, stepIdx) in reasoningSteps" :key="step.iteration || `step-${stepIdx}`" class="reasoning-step">
                        <div v-if="step.type === 'thought' || step.type === 'task_start'" class="step-thought">
                          <div class="step-header">
                            <v-icon size="14" color="blue" class="mr-1">mdi-lightbulb</v-icon>
                            <span class="step-iteration">Step {{ step.iteration || stepIdx + 1 }}</span>
                            <v-chip v-if="step.confidence" size="x-small" :color="step.confidence >= 0.8 ? 'success' : step.confidence >= 0.5 ? 'warning' : 'error'" class="ml-2">
                              {{ (step.confidence * 100).toFixed(0) }}%
                            </v-chip>
                  </div>
                          <div class="step-content-full">{{ step.content || step.thought || '' }}</div>
                  </div>
                        <div v-else-if="step.type === 'tool_start' || step.type === 'tool_call'" class="step-tool">
                          <div class="step-header">
                            <v-icon size="14" color="orange" class="mr-1">mdi-wrench</v-icon>
                            <span class="tool-name">{{ step.tool_name || 'Tool' }}</span>
                            <span class="step-iteration">Step {{ step.iteration || stepIdx + 1 }}</span>
                </div>
                          <div v-if="step.tool_args && Object.keys(step.tool_args).length > 0" class="tool-args">
                            <details class="tool-args-details">
                              <summary>Arguments</summary>
                              <pre>{{ JSON.stringify(step.tool_args, null, 2) }}</pre>
                            </details>
              </div>
                          <div v-if="step.result" class="tool-result" :class="{ 'tool-success': !step.result?.includes('Error'), 'tool-error': step.result?.includes('Error') }">
                            <strong>Result:</strong> {{ step.result }}
                </div>
                          <div v-else-if="step.type === 'tool_start'" class="tool-pending">
                            <v-progress-circular indeterminate size="12" color="orange" class="mr-1"></v-progress-circular>
                            <span>Executing...</span>
                  </div>
                  </div>
                        <div v-else-if="step.type === 'complete'" class="step-complete">
                          <v-icon size="14" color="success" class="mr-1">mdi-check-circle</v-icon>
                          <span class="step-content-full">{{ step.content || 'Task completed' }}</span>
                  </div>
                        <div v-else-if="step.type === 'error'" class="step-error">
                          <v-icon size="14" color="error" class="mr-1">mdi-alert-circle</v-icon>
                          <span class="step-content-full">{{ step.content || 'Error occurred' }}</span>
                </div>
              </div>
                </div>
                    <v-btn v-if="reasoningSteps.length > 0" size="x-small" variant="text" @click="clearReasoningSteps" class="mt-2">
                      Clear All
                    </v-btn>
                  </div>
                  </div>
                  </div>
                </div>
              </div>

          <!-- Agent Status at bottom -->
          <div class="studio-section" style="margin-top: auto;">
            <h4 class="section-title">Agent Status:</h4>
            <div class="agent-status">
              <v-chip color="success" size="small">SparksBM Agent Ready</v-chip>
            </div>
          </div>
        </div>
        <div v-else class="panel-collapsed-content">
          <v-btn icon variant="text" @click="rightCollapsed = false">
            <v-icon>mdi-menu</v-icon>
          </v-btn>
        </div>
      </div>
    </div>


    <!-- Footer -->
    <div class="notebook-footer">
      SparksBM Agent can be inaccurate; please double check its responses.
    </div>
    </div>
  </v-app>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import LayoutAppLogoDesktop from '~/components/layout/AppLogoDesktop.vue'

const leftCollapsed = ref(false)
const rightCollapsed = ref(false)

// Chat content ref for auto-scrolling
const chatContentRef = ref<HTMLElement | null>(null)

// Panel widths (in pixels)
const leftPanelWidth = ref(300)
const rightPanelWidth = ref(400)

// Resize state
const isResizing = ref(false)
const resizeType = ref<'left' | 'right' | null>(null)

const sources = ref<Array<{id: string, name: string, type: string, url?: string}>>([])
const chatHistory = ref<Array<{
  id?: string
  role: string
  content: string
  isTable?: boolean
  tableColumns?: string[]
  tableData?: any[]
  tableTotal?: number
}>>([])

const isProcessing = ref(false)

const formatMessage = (text: string): string => {
  // Convert markdown-style formatting to HTML
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
}

const generateMessageId = (): string => {
  return `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
}

// Auto-scroll to bottom when new messages are added
const scrollToBottom = () => {
  nextTick(() => {
    if (chatContentRef.value) {
      chatContentRef.value.scrollTop = chatContentRef.value.scrollHeight
    }
  })
}

// Watch chatHistory and auto-scroll when new messages are added
watch(chatHistory, () => {
  scrollToBottom()
}, { deep: true })

const currentMessage = ref('')

const chatInputPlaceholder = computed(() => {
  return 'Type your message...'
})
const sessionId = ref<string | null>(null)
const eventSource = ref<EventSource | null>(null)
const isRestoring = ref(false) // Flag to prevent saving during restoration
const isReconnecting = ref(false) // Flag to prevent duplicate SSE reconnections

// Agent Processing state
const reasoningSteps = ref<Array<{
  type: 'thought' | 'tool_call' | 'tool_start' | 'task_start' | 'complete' | 'error',
  iteration?: number,
  content?: string,
  thought?: string,
  action?: string,
  tool_name?: string,
  tool_args?: Record<string, any>,
  result?: string,
  confidence?: number
}>>([])

// Collapsed state for categories
const collapsedCategories = ref({
  agentProcessing: false,  // Auto-expand when agent is working
  reasoningSteps: false   // Auto-expand reasoning steps
})

const config = useRuntimeConfig()
const API_BASE = config.public.apiBase as string

const createSession = async (): Promise<string | null> => {
  try {
    const response = await $fetch<{ status: string; sessionId?: string; error?: string }>(`${API_BASE}/api/agent/session`, {
      method: 'POST',
      params: { userId: 'default' }
    })
    if (response.status === 'success' && response.sessionId) {
    sessionId.value = response.sessionId
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem('notebook_session_id', response.sessionId)
      }
      return response.sessionId
    } else {
      console.error('Failed to create session:', response.error || 'Unknown error')
      // Issue #8: Show user feedback on session creation failure
    chatHistory.value.push({
        id: generateMessageId(),
        role: 'assistant',
        content: `⚠️ Failed to create session: ${response.error || 'Unknown error'}. Please refresh the page.`
      })
      return null
    }
  } catch (e: any) {
    console.error('Failed to create session:', e)
    // Issue #8: Show user feedback on session creation failure
        chatHistory.value.push({
          id: generateMessageId(),
          role: 'assistant',
      content: `⚠️ Session creation failed: ${e.message}. Please refresh the page.`
    })
    return null
  }
}

const removeSource = (sourceId: string) => {
  sources.value = sources.value.filter(s => s.id !== sourceId)
}

// ================== AGENT PROCESSING HANDLERS ==================

const clearReasoningSteps = () => {
  reasoningSteps.value = []
}


const connectEventStream = (sid: string) => {
  // Close existing connection if any
  if (eventSource.value) {
    eventSource.value.close()
  }
  
  // Connect to SSE stream
  const streamUrl = `${API_BASE}/api/agent/stream/${sid}`
  const es = new EventSource(streamUrl)
  
  es.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      
      // Handle different event types
      if (data.type === 'connected') {
        console.log('✅ Connected to agent event stream')
      } else if (data.type === 'heartbeat') {
        // Keep connection alive
      } else if (data.type === 'thought' || data.type === 'task_start' || data.type === 'clarification') {
        // Add thought to reasoning steps
        reasoningSteps.value.push({
          type: data.type === 'clarification' ? 'thought' : data.type,
          iteration: data.data?.iteration || reasoningSteps.value.length + 1,
          content: data.data?.content || data.data?.thought || data.data?.question || '',
          action: data.data?.action,
          confidence: data.data?.confidence
        })
        // Auto-expand Agent Processing panel and reasoning steps
        collapsedCategories.value.agentProcessing = false
        collapsedCategories.value.reasoningSteps = false
      } else if (data.type === 'tool_start') {
        // Add tool call to reasoning steps
        reasoningSteps.value.push({
          type: 'tool_start',
          iteration: data.data?.iteration || reasoningSteps.value.length + 1,
          tool_name: data.data?.tool_name || '',
          tool_args: data.data?.tool_args || {},
          result: undefined,
          confidence: data.data?.confidence
        })
        // Auto-expand reasoning steps
        collapsedCategories.value.reasoningSteps = false
      } else if (data.type === 'tool_complete') {
        // Update last tool call with result
        const lastToolIndex = reasoningSteps.value.length - 1
        if (lastToolIndex >= 0 && (reasoningSteps.value[lastToolIndex].type === 'tool_start' || reasoningSteps.value[lastToolIndex].type === 'tool_call')) {
          reasoningSteps.value[lastToolIndex].type = 'tool_call'
          reasoningSteps.value[lastToolIndex].result = data.data?.observation || data.data?.result || 'Completed'
        }
      } else if (data.type === 'complete') {
        reasoningSteps.value.push({
          type: 'thought',
          iteration: reasoningSteps.value.length + 1,
          content: data.data?.content || 'Task completed',
          action: 'complete'
        })
      } else if (data.type === 'error') {
        // Error occurred
        reasoningSteps.value.push({
          type: 'thought',
          iteration: reasoningSteps.value.length + 1,
          content: `Error: ${data.data?.message || data.message || 'Unknown error'}`,
          action: 'error'
        })
      }
    } catch (e) {
      console.error('Failed to parse SSE event:', e, event.data)
    }
  }
  
  es.onerror = (error) => {
    console.error('SSE connection error:', error)
    
    // Prevent multiple simultaneous reconnections
    if (isReconnecting.value) {
      console.log('Reconnection already in progress, skipping...')
      return
    }
    
    // Close existing connection
    if (eventSource.value) {
      eventSource.value.close()
      eventSource.value = null
    }
    
    // Set reconnection flag
    isReconnecting.value = true
    
    // Try to reconnect after delay
    setTimeout(() => {
      console.log('Attempting to reconnect SSE...')
      if (sessionId.value) {
        connectEventStream(sessionId.value)
      }
      isReconnecting.value = false
    }, 3000) // 3 second delay
  }
  
  eventSource.value = es
}

const sendMessage = async () => {
  if (!currentMessage.value.trim()) return
  
  if (!sessionId.value) {
    const newSessionId = await createSession()
    if (!newSessionId) {
      chatHistory.value.push({
        id: generateMessageId(),
        role: 'assistant',
        content: 'Error: Failed to create session. Please refresh the page.'
      })
      return
    }
  }
  
  // Connect to event stream if not already connected
  if (eventSource.value) {
    const state = eventSource.value.readyState
    // EventSource.CONNECTING = 0, OPEN = 1, CLOSED = 2
    if (state === EventSource.OPEN) {
      // Already connected, do nothing
    } else if (state === EventSource.CONNECTING) {
      console.log('SSE connection in progress, waiting...')
    } else if (state === EventSource.CLOSED && sessionId.value) {
      // Reconnect if closed
      connectEventStream(sessionId.value)
    }
  } else if (sessionId.value) {
    // No connection exists, create one
    connectEventStream(sessionId.value)
  }
  
  // Clear reasoning steps for new task
  reasoningSteps.value = []
  
  const userMsg = currentMessage.value.trim()
  if (!userMsg) return
  
  // Add user message to chat
  chatHistory.value.push({
    id: generateMessageId(),
    role: 'user',
    content: userMsg
  })
  
  // Clear input
  currentMessage.value = ''
  
  // Set processing state
  isProcessing.value = true
  
  // Issue #7: Add request timeout handling
  const controller = new AbortController()
  const timeoutId = setTimeout(() => {
    controller.abort()
  }, 60000) // 60 second timeout
  
  try {
    // Get active sources for context
    const activeSources = sources.value.map(s => ({
      id: s.id,
      name: s.name,
      type: s.type,
      domainId: '',
      data: {}
    }))
    
    const response = await $fetch<{ 
      status: string
      result?: string | {
        type: 'table' | 'object_detail'
        title?: string
        columns?: string[]
        data?: any[]
        [key: string]: any
      }
      dataType?: 'table' | 'object_detail'
      error?: string 
    }>(`${API_BASE}/api/agent/chat`, {
      method: 'POST',
      body: {
        message: userMsg,
        sources: activeSources,
        sessionId: sessionId.value
      }
      // Note: Long requests may take time. Consider using AbortSignal for timeout control.
    })
    
    if (response.status === 'error') {
      chatHistory.value.push({
        id: generateMessageId(),
        role: 'assistant',
        content: `Error: ${response.error || 'Unknown error'}`
      })
    } else {
      // Handle structured data (tables) or plain text
      if (response.dataType === 'table' && typeof response.result === 'object' && response.result !== null) {
        // Render as HTML table
        const tableData = response.result as any
      chatHistory.value.push({
        role: 'assistant',
          content: tableData.title || 'Data',
          isTable: true,
          tableColumns: tableData.columns || [],
          tableData: (tableData.data || tableData.items || []).slice(0, 20),
          tableTotal: tableData.total || (tableData.data || tableData.items || []).length
        })
      } else {
        // Handle agent responses
        if (typeof response.result === 'object' && response.result !== null) {
          const result = response.result as any
          
          if (result.type === 'agent_response' || result.type === 'agent_clarification' || result.type === 'agent_error') {
            // Extract and display reasoning steps
            if (result.reasoning_steps && Array.isArray(result.reasoning_steps)) {
              // Merge with existing steps (don't replace, in case SSE already added some)
              const existingIds = new Set(reasoningSteps.value.map((s: any) => s.iteration))
              result.reasoning_steps.forEach((step: any) => {
                if (!existingIds.has(step.iteration)) {
                  reasoningSteps.value.push(step)
                }
              })
              // Auto-expand the Agent Processing panel when there are steps
              collapsedCategories.value.agentProcessing = false
              collapsedCategories.value.reasoningSteps = false
            }
          }
        }
        
        // Handle normal response
        const content = typeof response.result === 'string' ? response.result : JSON.stringify(response.result)
        chatHistory.value.push({
          id: generateMessageId(),
          role: 'assistant',
          content: content || 'No response',
          isTable: false
        })
      }
    }
  } catch (e: any) {
    console.error('Chat error:', e)
    const errorMsg = e?.message || e?.data?.detail || String(e)
    const isTimeout = errorMsg.toLowerCase().includes('timeout') || errorMsg.toLowerCase().includes('aborted')
    chatHistory.value.push({
      id: generateMessageId(),
      role: 'assistant',
      content: `Error: ${errorMsg}${isTimeout ? ' (Request took too long. Try waiting or use a simpler query.)' : '\n\nPlease check:\n1. NotebookLLM API is running (http://localhost:8000)\n2. ISMS backend is running (http://localhost:8070)\n3. Network connection is working'}`
    })
  } finally {
    isProcessing.value = false
}
}

// Resize handlers
const startResize = (type: 'left' | 'right') => {
  isResizing.value = true
  resizeType.value = type
  document.addEventListener('mousemove', handleResize)
  document.addEventListener('mouseup', stopResize)
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
}

const handleResize = (e: MouseEvent) => {
  if (!isResizing.value || !resizeType.value) return
  
  const container = document.querySelector('.panel-container') as HTMLElement
  if (!container) return
  
  const containerRect = container.getBoundingClientRect()
  const containerWidth = containerRect.width
  const gap = 16 // gap between panels
  const dividerWidth = 4
  
  if (resizeType.value === 'left') {
    const newLeftWidth = e.clientX - containerRect.left - gap
    const minWidth = 200
    const maxWidth = containerWidth * 0.5
    
    if (newLeftWidth >= minWidth && newLeftWidth <= maxWidth) {
      leftPanelWidth.value = newLeftWidth
    }
  } else if (resizeType.value === 'right') {
    const newRightWidth = containerRect.right - e.clientX - gap
    const minWidth = 200
    const maxWidth = containerWidth * 0.5
    
    if (newRightWidth >= minWidth && newRightWidth <= maxWidth) {
      rightPanelWidth.value = newRightWidth
    }
  }
}

const stopResize = () => {
  isResizing.value = false
  resizeType.value = null
  document.removeEventListener('mousemove', handleResize)
  document.removeEventListener('mouseup', stopResize)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}

// Chat history is NOT saved to localStorage - it's session-only

// Save sources to localStorage
const saveSources = () => {
  if (isRestoring.value) return // Don't save during restoration
  if (typeof localStorage !== 'undefined' && sessionId.value) {
    try {
      localStorage.setItem(`notebook_sources_${sessionId.value}`, JSON.stringify(sources.value))
    } catch (e: any) {
      // Issue #11: Handle localStorage quota exceeded
      if (e.name === 'QuotaExceededError') {
        console.warn('localStorage quota exceeded, clearing old data...')
        
        // Clear old session data (only sources, not chat history)
        const keysToRemove: string[] = []
        for (let i = 0; i < localStorage.length; i++) {
          const key = localStorage.key(i)
          if (key && (key.startsWith('notebook_old_') || key.startsWith('notebook_sources_'))) {
            // Keep current session data
            if (!key.includes(sessionId.value!)) {
              keysToRemove.push(key)
            }
          }
        }
        
        // Remove old data
        keysToRemove.forEach(k => localStorage.removeItem(k))
        
        // Retry save
        try {
          localStorage.setItem(`notebook_sources_${sessionId.value}`, JSON.stringify(sources.value))
        } catch {
          // Show warning to user
          chatHistory.value.push({
            id: generateMessageId(),
            role: 'assistant',
            content: '⚠️ Storage full. Some data may not be saved. Please clear browser data or use fewer sessions.'
          })
        }
      } else {
        console.warn('Failed to save sources:', e)
      }
    }
  }
}

// Chat history is NOT restored from localStorage - it's session-only
const restoreChatHistory = (sid: string) => {
  return false
}

// Restore sources from localStorage
const restoreSources = (sid: string) => {
  if (typeof localStorage !== 'undefined') {
    try {
      const saved = localStorage.getItem(`notebook_sources_${sid}`)
      if (saved) {
        const parsed = JSON.parse(saved)
        if (Array.isArray(parsed)) {
          sources.value = parsed
          console.log(`✅ Restored ${parsed.length} sources from localStorage`)
          return true
        }
      }
    } catch (e) {
      console.warn('Failed to restore sources:', e)
    }
  }
  return false
}

const restoreSession = async (sid: string): Promise<boolean> => {
  isRestoring.value = true // Set flag to prevent saving during restoration
  try {
    // Restore sources from localStorage (for active context)
    restoreSources(sid)
    
    // Then fetch from backend
    const response = await $fetch<any>(`${API_BASE}/api/agent/context/${sid}`)
    if (response.status === 'success') {
      // Restore sources from backend if available (may be more up-to-date)
      if (response.sources && Array.isArray(response.sources) && response.sources.length > 0) {
        sources.value = response.sources
      }
      
      // Save sources after restoration (context awareness, not chat history)
      saveSources()
      
      return true
    }
    return false
  } catch (error) {
    console.warn('Failed to restore session:', error)
    // Return true if we restored sources
    return sources.value.length > 0
  } finally {
    isRestoring.value = false // Clear flag after restoration
  }
}

// Auto-save sources when they change (context awareness, not chat history)
watch(sources, () => {
  saveSources()
}, { deep: true })

// Watch sessionId to save it when it changes
watch(sessionId, (newId) => {
  if (newId && typeof localStorage !== 'undefined') {
    localStorage.setItem('notebook_session_id', newId)
  }
})

onMounted(async () => {
  let restored = false
  if (typeof localStorage !== 'undefined') {
    const savedId = localStorage.getItem('notebook_session_id')
    if (savedId) {
      sessionId.value = savedId
      restored = await restoreSession(savedId)
      // Connect to event stream
      connectEventStream(savedId)
    }
  }
  
  if (!restored) {
    const newId = await createSession()
    if (newId) {
       // Try to load repo info for new session (persistent backend state)
       await restoreSession(newId)
       // Connect to event stream
       connectEventStream(newId)
    }
  }
})

// Cleanup on unmount
onUnmounted(() => {
  if (eventSource.value) {
    eventSource.value.close()
    eventSource.value = null
  }
})
</script>

<style scoped>
.notebook-layout {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: #0a0a0a;
}

.notebook-header {
  background-color: #1a1a1a;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  padding: 0.75rem 1.5rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 60px;
}

.header-left {
  display: flex;
  align-items: center;
}

.notebook-title {
  color: #e0e0e0;
  font-size: 1rem;
  font-weight: 500;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.header-btn {
  color: #e0e0e0 !important;
}

.panel-container {
  display: flex;
  height: calc(100vh - 60px - 40px);
  width: 100%;
  padding: 16px;
  padding-bottom: 40px;
  gap: 16px;
  background-color: #1a1a1a;
}

.panel {
  background-color: #212121;
  overflow-y: auto;
  transition: width 0.3s ease;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.05);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  padding: 1rem;
}

.panel-left {
  background-color: #212121;
}

.panel-center {
  flex: 1;
  min-width: 300px;
  display: flex;
  flex-direction: column;
  background-color: #212121;
  transition: all 0.3s ease;
}


.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.panel-right {
  background-color: #212121;
}

.panel-right-content {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.panel-divider {
  width: 4px;
  background-color: rgba(255, 255, 255, 0.1);
  cursor: col-resize;
  transition: background-color 0.2s ease;
  flex-shrink: 0;
}

.panel-divider:hover {
  background-color: rgba(255, 255, 255, 0.2);
}

.panel-divider:active {
  background-color: rgba(200, 21, 23, 0.5);
}


.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.header-controls {
  display: flex;
  gap: 0.25rem;
  align-items: center;
  margin-left: auto;
}

.header-control-btn {
  opacity: 0.7;
  transition: opacity 0.2s;
}

.header-control-btn:hover {
  opacity: 1;
}


.panel-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: #e0e0e0;
}

.panel-toggle-icon {
  width: 16px;
  height: 16px;
  cursor: pointer;
  opacity: 0.7;
  color: rgba(255, 255, 255, 0.6);
  transition: opacity 0.2s;
}

.panel-toggle-icon:hover {
  opacity: 1;
}

.panel-actions {
  display: flex;
  gap: 0.25rem;
}

.panel-divider {
  width: 2px;
  background-color: rgba(0, 0, 0, 0.08);
  cursor: col-resize;
  transition: background-color 0.2s;
}

.panel-divider:hover {
  background-color: rgba(0, 0, 0, 0.15);
}

.source-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 0.75rem;
  margin: 0.25rem 0;
  background-color: #2a2a2a;
  border-radius: 6px;
  font-size: 0.8rem;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.source-info {
  display: flex;
  align-items: center;
  flex: 1;
}

.source-name {
  color: #e0e0e0;
  font-weight: 500;
  display: block;
  font-size: 0.875rem;
}

.source-type {
  color: #999;
  font-size: 0.75rem;
  display: block;
  margin-top: 0.125rem;
}

.source-url {
  color: #666;
  font-size: 0.7rem;
  display: block;
  margin-top: 0.125rem;
  word-break: break-all;
  opacity: 0.8;
}

.empty-state {
  text-align: center;
  padding: 2rem;
  color: #999;
  font-size: 0.875rem;
}



.section-header {
  display: flex;
  align-items: center;
  padding: 0.625rem 0.75rem;
  margin-bottom: 0.5rem;
  font-size: 0.8125rem;
  font-weight: 600;
  color: #e0e0e0;
  user-select: none;
  transition: background-color 0.2s ease;
  line-height: 1;
}

.section-header .v-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  vertical-align: middle;
  flex-shrink: 0;
}

.section-header .section-title {
  display: inline-block;
  line-height: 1;
  vertical-align: middle;
  margin: 0;
  padding: 0;
}

.section-header.clickable {
  cursor: pointer;
}

.section-header.clickable:hover {
  background-color: rgba(255, 255, 255, 0.03);
  border-radius: 4px;
}

.chevron-icon {
  transition: transform 0.2s ease;
  color: rgba(255, 255, 255, 0.6);
  flex-shrink: 0;
  width: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.section-header .section-title {
  margin-left: 0.25rem;
  flex: 1;
  display: inline-block;
  line-height: 1;
  vertical-align: middle;
}

.section-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
  transition: opacity 0.2s ease;
}


.chat-content {
  flex: 1;
  padding: 1rem;
  overflow-y: auto;
}

.empty-chat {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 1rem;
}

.empty-chat h3 {
  color: #e0e0e0;
  font-weight: 500;
}

.empty-chat .text-caption {
  color: #999;
}


.messages {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.message {
  padding: 0.75rem 1rem;
  border-radius: 12px;
  font-size: 0.875rem;
  line-height: 1.6;
  border: none;
}

.message.user {
  background-color: #2a2a2a;
  color: #e0e0e0;
  align-self: flex-end;
  max-width: 80%;
}

.message.assistant {
  background-color: #2a2a2a;
  color: #e0e0e0;
  align-self: flex-start;
  max-width: 80%;
}

.agent-label {
  font-weight: 600;
  color: #c81517;
  margin-right: 0.5rem;
}

.chat-input-container {
  padding: 1rem;
  padding-bottom: 1.5rem;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  background-color: #212121;
  position: sticky;
  bottom: 0;
  z-index: 10;
  margin: 0 -1rem -1rem -1rem;
  padding-left: 1rem;
  padding-right: 1rem;
}


.chat-input-row {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  width: 100%;
}


.chat-input-field {
  flex: 1;
}

.chat-input-container :deep(.v-field) {
  background-color: #2a2a2a !important;
  border-color: rgba(255, 255, 255, 0.2) !important;
}

.chat-input-container :deep(.v-field__input) {
  color: #e0e0e0 !important;
}

.chat-input-container :deep(.v-field__input::placeholder) {
  color: #999 !important;
  opacity: 1 !important;
}

.chat-input-container :deep(.v-field:hover) {
  border-color: rgba(255, 255, 255, 0.3) !important;
}

.chat-input-container :deep(.v-field--focused) {
  border-color: rgba(255, 255, 255, 0.4) !important;
}

.studio-section {
  margin-bottom: 0;
}

.section-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: #e0e0e0;
  margin-bottom: 0.75rem;
}

.tools-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.tool-item {
  display: flex;
  align-items: flex-start;
  padding: 0.75rem;
  background-color: #2a2a2a;
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 6px;
  transition: background-color 0.2s;
}

.tool-item :deep(.v-icon) {
  color: #ffffff !important;
}

.tool-item.clickable {
  cursor: pointer;
}

.tool-item.clickable:hover {
  background-color: #2f2f2f;
  border-color: rgba(200, 21, 23, 0.5);
}

.tool-category {
  margin-bottom: 1.5rem;
}

.category-title {
  font-size: 0.75rem;
  font-weight: 600;
  color: #999;
  margin-bottom: 0.5rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: flex;
  align-items: center;
}

.category-title.clickable {
  cursor: pointer;
  user-select: none;
  transition: color 0.2s;
}

.category-title.clickable:hover {
  color: #e0e0e0;
}

.tool-subcategory {
  margin-left: 0.5rem;
  margin-bottom: 1rem;
  padding-left: 0.75rem;
  border-left: 2px solid rgba(255, 255, 255, 0.08);
}

.tool-object-type {
  margin-left: 0.5rem;
  margin-bottom: 0.75rem;
  padding-left: 0.5rem;
}

.object-type-title {
  display: flex;
  align-items: center;
  padding: 0.5rem 0.75rem;
  color: #e0e0e0;
  font-size: 0.875rem;
  font-weight: 500;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.object-type-title :deep(.v-icon) {
  color: #ffffff !important;
}

.object-type-title.clickable {
  cursor: pointer;
}

.object-type-title.clickable:hover {
  background-color: #2a2a2a;
}

.object-tools-list {
  margin-left: 1rem;
  margin-top: 0.25rem;
  padding-left: 0.75rem;
  border-left: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.subcategory-title {
  font-size: 0.8125rem;
  font-weight: 600;
  color: #e0e0e0;
  margin-bottom: 0.5rem;
  display: flex;
  align-items: center;
  text-transform: none;
}

.subcategory-title :deep(.v-icon) {
  color: #ffffff !important;
}

.subcategory-title.clickable {
  cursor: pointer;
  user-select: none;
  transition: color 0.2s;
}

.subcategory-title.clickable:hover {
  color: #ffffff;
}

.tool-info {
  flex: 1;
}

.tool-name {
  color: #ffffff;
  font-weight: 500;
  font-size: 0.875rem;
  margin-bottom: 0.25rem;
}

.tool-desc {
  color: #e0e0e0;
  font-size: 0.75rem;
}

.agent-status {
  padding: 0.75rem;
  background-color: #2a2a2a;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.isms-menu {
  margin-top: 1rem;
}

.isms-menu .menu-category {
  margin-bottom: 0;
}

/* Agent Processing Panel Styles */
.agent-processing-panel {
  padding: 0.5rem;
  font-size: 0.75rem;
}

.subsection-title {
  font-size: 0.7rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.7);
  margin-bottom: 0.5rem;
  display: flex;
  align-items: center;
}

.subsection-title.clickable {
  cursor: pointer;
  user-select: none;
  transition: color 0.2s;
}

.subsection-title.clickable:hover {
  color: rgba(255, 255, 255, 0.9);
}


.reasoning-section {
  padding: 0.5rem;
}

.no-steps {
  font-size: 0.7rem;
  font-style: italic;
  padding: 0.5rem 0;
}

.reasoning-steps-list {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  max-height: 200px;
  overflow-y: auto;
}

.reasoning-step {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.03);
  font-size: 0.7rem;
  line-height: 1.3;
}

.step-thought {
  display: flex;
  align-items: flex-start;
  color: #90caf9;
}

.step-tool {
  display: flex;
  flex-direction: column;
  color: #ffb74d;
}

.tool-name {
  font-family: 'Monaco', 'Courier New', monospace;
  font-weight: 600;
}

.tool-result {
  font-size: 0.65rem;
  margin-top: 0.15rem;
  padding-left: 1.25rem;
  color: rgba(255, 255, 255, 0.6);
}

.tool-success {
  color: #81c784;
}

.tool-error {
  color: #ef5350;
}

.isms-menu .category-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: #ffffff;
  padding: 0.5rem 0.75rem;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.isms-menu .category-title.clickable:hover {
  background-color: rgba(255, 255, 255, 0.05);
}

.isms-menu .menu-items {
  margin-left: 0.5rem;
  margin-top: 0.25rem;
  padding-left: 0.5rem;
  border-left: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.isms-menu .menu-item {
  display: flex;
  align-items: center;
  padding: 0.5rem 0.75rem;
  color: #ffffff;
  font-size: 0.875rem;
}

.isms-menu .menu-item span {
  color: #ffffff !important;
}

.isms-menu .menu-item :deep(.v-icon) {
  color: #ffffff !important;
  font-size: 0.875rem;
  border-radius: 4px;
  transition: background-color 0.2s;
  cursor: pointer;
  user-select: none;
}

.isms-menu .menu-item:hover {
  background-color: rgba(255, 255, 255, 0.05);
  color: #ffffff;
}

.isms-menu .menu-item :deep(.v-icon) {
  color: #e0e0e0;
}

.isms-menu .menu-item:hover :deep(.v-icon) {
  color: #ffffff;
}

/* Menu styling - same as ISMS menu */
.studio-section .menu-items {
  margin-left: 0.5rem;
  margin-top: 0.25rem;
  padding-left: 0.5rem;
  border-left: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.studio-section .menu-item {
  display: flex;
  align-items: center;
  padding: 0.5rem 0.75rem;
  color: #ffffff;
  font-size: 0.875rem;
}

.studio-section .menu-item span {
  color: #ffffff !important;
}

.studio-section .menu-item :deep(.v-icon) {
  color: #ffffff !important;
  font-size: 0.875rem;
}

.studio-section .menu-item.clickable {
  cursor: pointer;
  user-select: none;
}

.studio-section .menu-item.clickable:hover {
  background-color: rgba(255, 255, 255, 0.05);
  color: #ffffff;
}

.studio-section .menu-item.clickable:hover :deep(.v-icon) {
  color: #ffffff;
}

.studio-section .category-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: #ffffff;
  padding: 0.5rem 0.75rem;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.studio-section .category-title.clickable:hover {
  background-color: rgba(255, 255, 255, 0.05);
}

.loading-spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(255, 255, 255, 0.1);
  border-top-color: #c81517;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto 0.5rem;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-state {
  text-align: center;
  padding: 1rem;
}

.error-text {
  color: #ff6b6b;
  font-size: 0.875rem;
  margin: 0.5rem 0;
}

.empty-outputs {
  padding: 1rem;
  background-color: #2a2a2a;
  border-radius: 6px;
  color: #999;
  font-size: 0.875rem;
  text-align: center;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.panel-collapsed-content {
  padding: 0.5rem;
  display: flex;
  justify-content: center;
}

.notebook-footer {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background-color: #1a1a1a;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding: 0.5rem;
  text-align: center;
  font-size: 0.75rem;
  color: #999;
  height: 40px;
  z-index: 5;
}

.message-text {
  white-space: pre-wrap;
  word-wrap: break-word;
  overflow-wrap: break-word;
  max-width: 100%;
  /* Ensure full content is visible - no height restrictions */
  overflow: visible;
}

.table-container {
  margin: 0.5rem 0;
  overflow-x: auto;
  overflow-y: visible;
  max-width: 100%;
  width: 100%;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.3) rgba(0, 0, 0, 0.1);
}

.table-container::-webkit-scrollbar {
  height: 8px;
}

.table-container::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.1);
  border-radius: 4px;
}

.table-container::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.3);
  border-radius: 4px;
}

.table-container::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.5);
}

.data-table {
  width: 100%;
  min-width: max-content;
  border-collapse: collapse;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background-color: #2a2a2a;
  font-size: 0.875rem;
  white-space: nowrap;
}

.data-table thead {
  background-color: #1a1a1a;
}

.data-table th {
  padding: 0.75rem;
  text-align: left;
  font-weight: 600;
  color: #ffffff;
  border-bottom: 2px solid rgba(255, 255, 255, 0.2);
  border-right: 1px solid rgba(255, 255, 255, 0.1);
}

.data-table th:last-child {
  border-right: none;
}

.data-table td {
  padding: 0.75rem;
  color: #e0e0e0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  border-right: 1px solid rgba(255, 255, 255, 0.1);
  white-space: nowrap;
}

.data-table td:last-child {
  border-right: none;
}

.data-table tbody tr:hover {
  background-color: rgba(255, 255, 255, 0.05);
}

.data-table tbody tr:last-child td {
  border-bottom: none;
}

.table-footer {
  padding: 0.5rem 0.75rem;
  color: #999;
  font-size: 0.8125rem;
  font-style: italic;
}

.file-content code {
  font-family: inherit;
  color: inherit;
  background: transparent;
  padding: 0;
}

/* Diff View Styles (Inline highlights) */
.file-diff-view {
  font-family: 'Monaco', 'Courier New', monospace;
  font-size: 0.75rem;
  line-height: 1.5;
  background: rgba(0, 0, 0, 0.4);
}

.diff-line {
  display: flex;
  align-items: center;
  padding: 0.125rem 0.75rem;
  border-left: 3px solid transparent;
  white-space: pre;
}

.diff-line-context {
  background: rgba(255, 255, 255, 0.02);
  color: #e0e0e0;
}

.diff-line-add {
  background: rgba(76, 175, 80, 0.15);
  border-left-color: #4caf50;
  color: #a5d6a7;
}

.diff-line-remove {
  background: rgba(244, 67, 54, 0.15);
  border-left-color: #f44336;
  color: #ef9a9a;
}

.diff-line-number {
  display: inline-block;
  width: 3rem;
  text-align: right;
  padding-right: 0.5rem;
  color: #666;
  font-size: 0.7rem;
  user-select: none;
  flex-shrink: 0;
}

.diff-line-marker {
  display: inline-block;
  width: 1rem;
  text-align: center;
  font-weight: bold;
  flex-shrink: 0;
}

.diff-line-content {
  flex: 1;
  padding-left: 0.5rem;
  overflow-x: auto;
}

.diff-line-add .diff-line-marker {
  color: #4caf50;
}

.diff-line-remove .diff-line-marker {
  color: #f44336;
}
</style>
