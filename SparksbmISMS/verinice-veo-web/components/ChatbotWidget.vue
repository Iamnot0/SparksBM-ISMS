<!--
   - SparksBM Chatbot Widget Component
   - Embeds NotebookLLM chatbot on the login/welcome page
-->
<template>
  <div class="chatbot-widget">
    <!-- Toggle Button (Floating) - Message Icon -->
    <button
      v-if="!isOpen"
      class="chatbot-toggle"
      aria-label="Open chatbot"
      @click="isOpen = true"
    >
      <svg class="toggle-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path :d="mdiMessageTextOutline" fill="currentColor" />
      </svg>
    </button>

    <!-- Chat Window -->
    <v-card
      v-if="isOpen"
      class="chatbot-window"
      elevation="8"
    >
      <div class="chatbot-header">
        <div class="header-left">
          <div class="header-logo">
            <img 
              src="/logo.png" 
              alt="SparksBM" 
              class="header-logo-img"
            />
            <span class="header-title">Chat</span>
          </div>
        </div>
        <button
          class="close-btn"
          aria-label="Close chatbot"
          @click="isOpen = false"
        >
          <svg class="close-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path :d="mdiClose" fill="currentColor" />
          </svg>
        </button>
        </div>
        
      <v-card-text ref="messagesContainer" class="chatbot-messages pa-0">
        <div
          v-for="(msg, idx) in messages"
          :key="idx"
          :class="['message', msg.role]"
        >
          <div class="message-wrapper">
            <div v-if="msg.isTable" class="table-container">
              <div v-if="msg.tableTitle" class="table-title">{{ msg.tableTitle }}</div>
              <table class="data-table">
                <thead>
                  <tr>
                    <th v-for="col in msg.tableColumns" :key="col">{{ col }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, rowIdx) in msg.tableData" :key="rowIdx">
                    <td v-for="col in msg.tableColumns" :key="col">{{ (row as Record<string, any>)[col] || '-' }}</td>
                  </tr>
                </tbody>
              </table>
              <div v-if="msg.tableMore" class="table-more">{{ msg.tableMore }}</div>
            </div>
            <template v-else>
              <!-- eslint-disable-next-line vue/no-v-html -->
          <div class="message-content" v-html="formatMessage(msg.content)"></div>
            </template>
            <div v-if="msg.timestamp" class="message-timestamp">{{ formatTime(msg.timestamp) }}</div>
          </div>
        </div>
        
        <div v-if="isLoading" class="loading-indicator">
          <div class="message assistant">
            <div class="message-wrapper">
              <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        </div>
      </v-card-text>

      <v-card-actions class="chatbot-input pa-2">
        <div class="input-wrapper">
        <v-text-field
          v-model="currentMessage"
          placeholder="Type your message or paste GitHub URL (e.g., https://github.com/user/repo)..."
          variant="outlined"
          density="compact"
          hide-details
          :disabled="isLoading || !sessionId"
            class="message-input"
          @keyup.enter="sendMessage"
        />
          <button
            class="send-btn"
            aria-label="Send message"
          :disabled="!currentMessage.trim() || isLoading || !sessionId"
          @click="sendMessage"
        >
            <svg class="send-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path :d="mdiSend" fill="currentColor" />
            </svg>
          </button>
        </div>
      </v-card-actions>
    </v-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, watch } from 'vue'
import { mdiMessageTextOutline, mdiClose, mdiSend } from '@mdi/js'

const isOpen = ref(false)
const messages = ref<Array<{
  role: string
  content: string
  timestamp?: Date
  isTable?: boolean
  tableTitle?: string
  tableColumns?: string[]
  tableData?: any[]
  tableMore?: string
}>>([])
const currentMessage = ref('')
const sessionId = ref<string | null>(null)
const isLoading = ref(false)
const messagesContainer = ref<HTMLElement | null>(null)
const connectionError = ref(false)


// API Configuration - Get from runtime config
const config = useRuntimeConfig()
const API_BASE = (config.public.notebookllmApiUrl as string) || 'http://localhost:8000'

const checkBackendHealth = async (): Promise<boolean> => {
  try {
    const response = await $fetch<{ status: string }>(`${API_BASE}/health`, {
      method: 'GET',
      timeout: 3000 // 3 second timeout
    })
    return response?.status === 'healthy'
  } catch (error: any) {
    // Check if it's a connection error (server not running)
    if (error?.code === 'ECONNREFUSED' || error?.message?.includes('fetch') || error?.statusCode === undefined) {
      return false
    }
    return false
  }
}

const createSession = async (): Promise<boolean> => {
  try {
    // First check if backend is accessible
    const isHealthy = await checkBackendHealth()
    if (!isHealthy) {
      connectionError.value = true
      const errorMsg = `⚠️ Backend API at ${API_BASE} is not accessible.\n\nTo start the NotebookLLM API server, run:\n\n  cd /home/clay/Desktop/SparksBM/NotebookLLM\n  ./start.sh\n\nOr manually start the API:\n  cd /home/clay/Desktop/SparksBM/NotebookLLM\n  uvicorn api.main:app --reload --port 8000`
      
      messages.value.push({
        role: 'assistant',
        content: errorMsg,
        timestamp: new Date()
      })
      return false
    }
    
    const response = await $fetch<{ status: string, sessionId: string, error?: string }>(`${API_BASE}/api/agent/session`, {
      method: 'POST',
      params: { userId: 'default' },
      timeout: 10000 // 10 second timeout
    })
    
    if (response?.status === 'success' && response?.sessionId) {
      sessionId.value = response.sessionId
      connectionError.value = false
      return true
    } else {
      const errorMsg = response?.error || 'Invalid session response'
      throw new Error(errorMsg)
    }
  } catch (error: any) {
    connectionError.value = true
    let errorMsg = error?.message || error?.data?.detail || 'Failed to create session'
    
    // Provide more helpful error messages
    if (errorMsg.includes('NetworkError') || errorMsg.includes('fetch') || error?.code === 'ECONNREFUSED') {
      errorMsg = `⚠️ Cannot connect to backend API at ${API_BASE}.\n\nPlease ensure:\n1. The NotebookLLM API server is running\n2. Start it with: cd /home/clay/Desktop/SparksBM/NotebookLLM && ./start.sh\n3. The API is accessible at ${API_BASE}\n4. There are no firewall or network issues`
    } else if (errorMsg.includes('CORS')) {
      errorMsg = `CORS error: The backend API is not allowing requests from this origin. Please check CORS configuration.`
    }
    
    messages.value.push({
      role: 'assistant',
      content: errorMsg,
      timestamp: new Date()
    })
    return false
  }
}

// Detect GitHub URL in message and convert to "load repo" command
const detectAndProcessGitHubUrl = (message: string): string => {
  // Check if message contains a GitHub URL
  const githubUrlPattern = /https?:\/\/(?:www\.)?github\.com\/[\w.-]+\/[\w.-]+(?:\/.*)?/i
  const urlMatch = message.match(githubUrlPattern)
  
  if (urlMatch) {
    const githubUrl = urlMatch[0]
    // If message is just the URL or starts with URL, convert to "load repo" command
    const trimmedMessage = message.trim()
    if (trimmedMessage === githubUrl || trimmedMessage.startsWith(githubUrl)) {
      return `load repo ${githubUrl}`
    }
    // If message contains "load repo" or similar, keep as is
    if (trimmedMessage.toLowerCase().includes('load repo') || 
        trimmedMessage.toLowerCase().includes('load repository') ||
        trimmedMessage.toLowerCase().includes('clone')) {
      return message // Already has load command
    }
    // Otherwise, prepend "load repo" to the URL
    return `load repo ${githubUrl}`
  }
  
  return message // No GitHub URL found, return original message
}

const sendMessage = async () => {
  if (!currentMessage.value.trim() || isLoading.value) return
  
  // Create session if it doesn't exist
  if (!sessionId.value) {
    const sessionCreated = await createSession()
    if (!sessionCreated) {
      // Error message already shown in createSession
      return
    }
  }
  
  let userMsg = currentMessage.value.trim()
  
  // Detect and process GitHub URLs - convert to "load repo" command
  userMsg = detectAndProcessGitHubUrl(userMsg)
  
  messages.value.push({ role: 'user', content: currentMessage.value.trim(), timestamp: new Date() })
  currentMessage.value = ''
  isLoading.value = true
  
  await nextTick()
  scrollToBottom()
  
  try {
    const response = await $fetch<{
      status: string
      result?: string | any
      error?: string
      dataType?: string
      type?: string
      repository?: any
    }>(`${API_BASE}/api/agent/chat`, {
      method: 'POST',
      body: {
        message: userMsg,
        sessionId: sessionId.value,
        sources: [] // No document sources - only GitHub repos via chat
      }
    })
    
    if (response.status === 'success') {
      // Check if this is a repository_loaded response FIRST
      let repoData = null
      let responseType = null
      let repositoryContent = ''
      
      // PRIORITY 1: Check direct properties on response (top level)
      if (response.type === 'repository_loaded' && response.repository) {
        responseType = 'repository_loaded'
        repoData = response.repository
        repositoryContent = typeof response.result === 'string' ? response.result : (response.result as any)?.content || `Successfully loaded repository: ${repoData.name}`
      }
      // PRIORITY 2: Check in result object (nested structure)
      else if (typeof response.result === 'object' && response.result !== null) {
        const result = response.result as any
        if (result.type === 'repository_loaded' && result.repository) {
          responseType = 'repository_loaded'
          repoData = result.repository
          repositoryContent = result.content || `Successfully loaded repository: ${repoData.name}`
        }
        else if (result.repository && typeof result.repository === 'object') {
          responseType = 'repository_loaded'
          repoData = result.repository
          repositoryContent = result.content || `Successfully loaded repository: ${repoData.name}`
        }
      }
      
      // Process repository_loaded response
      if (responseType === 'repository_loaded' && repoData) {
        
        // Show repository loaded message
        messages.value.push({
          role: 'assistant',
          content: repositoryContent || `✅ Successfully loaded repository: **${repoData.name}**\n\nRepository Information:\n  • URL: ${repoData.url}\n  • Files: ${repoData.file_count}\n  • Code Files: ${repoData.code_files}\n\nThe repository is now loaded and ready for analysis.`,
          timestamp: new Date()
        })
      }
      // Check if response is a structured table
      else if (response.dataType === 'table' && typeof response.result === 'object') {
        const table = response.result as any
        messages.value.push({
          role: 'assistant',
          content: '',
          isTable: true,
          tableTitle: table.title || 'Data',
          tableColumns: table.columns || [],
          tableData: (table.data || []).slice(0, 50),
          tableMore: table.data && table.data.length > 50 ? `... and ${table.data.length - 50} more rows` : undefined,
          timestamp: new Date()
        })
      } else if (typeof response.result === 'string') {
        // Check if string contains markdown table
        const tableData = parseMarkdownTable(response.result)
        if (tableData && tableData.columns && tableData.data) {
          messages.value.push({
            role: 'assistant',
            content: tableData.remaining || '',
            isTable: true,
            tableTitle: tableData.title,
            tableColumns: tableData.columns,
            tableData: tableData.data.slice(0, 50),
            tableMore: tableData.data.length > 50 ? `... and ${tableData.data.length - 50} more rows` : undefined,
            timestamp: new Date()
          })
        } else {
          messages.value.push({ role: 'assistant', content: response.result, timestamp: new Date() })
        }
      } else {
        messages.value.push({ role: 'assistant', content: JSON.stringify(response.result), timestamp: new Date() })
      }
    } else {
      const errorMsg = response.error || 'Unknown error'
      // Remove any existing error prefixes and use message as-is
      const cleanError = errorMsg.replace(/^❌\s*Error:?\s*/i, '').replace(/^Error:\s*/i, '').trim()
      messages.value.push({
        role: 'assistant',
        content: cleanError,
        timestamp: new Date()
      })
    }
    
    await nextTick()
    scrollToBottom()
  } catch (error: any) {
    console.error('Chat error:', error)
    const errorMsg = error?.message || error?.data?.detail || String(error)
    // Remove any existing error prefixes
    const cleanError = errorMsg.replace(/^❌\s*Error:?\s*/i, '').replace(/^Error:\s*/i, '').trim()
    messages.value.push({
      role: 'assistant',
      content: cleanError,
      timestamp: new Date()
    })
  } finally {
    isLoading.value = false
  }
}

const parseMarkdownTable = (text: string): {isTable: boolean, title?: string, columns?: string[], data?: any[], remaining?: string} | null => {
  // Detect markdown table pattern: | col1 | col2 | ... followed by |---|---| and data rows
  const lines = text.split('\n')
  let headerIdx = -1
  let separatorIdx = -1
  
  // Find header and separator rows
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim()
    if (line.startsWith('|') && line.endsWith('|') && headerIdx === -1) {
      headerIdx = i
    } else if (headerIdx !== -1 && line.match(/^\|[|\s-]+\|$/)) {
      separatorIdx = i
      break
    }
  }
  
  if (headerIdx === -1 || separatorIdx === -1) return null
  
  // Extract title (line before header if it has **text**)
  let title = ''
  if (headerIdx > 0) {
    const titleLine = lines[headerIdx - 1].trim()
    const titleMatch = titleLine.match(/\*\*(.+?)\*\*/)
    if (titleMatch) {
      title = titleMatch[1]
    }
  }
  
  // Parse header
  const headerLine = lines[headerIdx]
  const columns = headerLine.split('|').map(c => c.trim()).filter(c => c)
  if (columns.length === 0) return null
  
  // Parse data rows
  const rows: any[] = []
  for (let i = separatorIdx + 1; i < lines.length; i++) {
    const line = lines[i].trim()
    if (!line.startsWith('|') || !line.endsWith('|')) break
    
    const cells = line.split('|').map(c => c.trim()).filter((c, idx) => idx > 0 && idx <= columns.length)
    if (cells.length === columns.length) {
      const row: Record<string, string> = {}
      columns.forEach((col, idx) => {
        if (col) {
          row[col] = cells[idx] || '-'
        }
      })
      rows.push(row)
    }
  }
  
  if (rows.length === 0) return null
  
  // Get remaining text after table
  const lastRowIdx = separatorIdx + rows.length + 1
  const remaining = lines.slice(lastRowIdx).join('\n').trim()
  
  return {
    isTable: true,
    title: title || undefined,
    columns,
    data: rows,
    remaining: remaining || undefined
  }
}

const formatMessage = (text: string): string => {
  // Check if text contains a markdown table
  const tableData = parseMarkdownTable(text)
  if (tableData) {
    // Return text without table (table will be rendered separately)
    return tableData.remaining || text.replace(/.*\|.*\|.*/gs, '').trim()
  }
  
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>')
}

const formatTime = (date: Date): string => {
  const hours = date.getHours()
  const minutes = date.getMinutes()
  const ampm = hours >= 12 ? 'PM' : 'AM'
  const displayHours = hours % 12 || 12
  const displayMinutes = minutes.toString().padStart(2, '0')
  return `${displayHours}:${displayMinutes} ${ampm}`
}

const scrollToBottom = () => {
  if (messagesContainer.value) {
    nextTick(() => {
      const container = messagesContainer.value
      if (container) {
        container.scrollTop = container.scrollHeight
      }
    })
  }
}

// Watch for new messages and scroll
watch(() => messages.value.length, () => {
  scrollToBottom()
})

// Retry connection when widget opens
watch(isOpen, (newVal) => {
  if (newVal && !sessionId.value && !connectionError.value) {
    createSession()
  } else if (newVal && connectionError.value) {
    // Retry connection
    createSession()
  }
})

onMounted(() => {
  createSession()
})
</script>

<style scoped lang="scss">
.chatbot-widget {
  position: fixed;
  bottom: 100px;
  right: 20px;
  z-index: 9999;
}

.chatbot-toggle {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background: #c90000;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
  padding: 0;
  margin: 0;
  transition: transform 0.2s ease;
  
  &:hover {
    transform: scale(1.05);
  }
  
  &:active {
    transform: scale(0.95);
  }
  
  .toggle-icon {
    width: 28px;
    height: 28px;
    color: #ffffff;
    display: block;
  }
}

.chatbot-window {
  width: 380px;
  height: 550px;
  display: flex;
  flex-direction: column;
  border-radius: 12px;
  overflow: hidden;
  background: rgb(var(--v-theme-surface));
  color: rgb(var(--v-theme-on-surface));
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.15);
}

.chatbot-header {
  background: #c90000;
  color: #ffffff;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  min-height: 48px;
  flex-shrink: 0;
  
  .header-left {
    display: flex;
    align-items: center;
    flex: 1;
    background: transparent;
  }
  
    .header-logo {
      display: flex;
      align-items: center;
      gap: 8px;
      height: 24px;
      background: transparent !important;
      background-color: transparent !important;
      padding: 0;
      margin: 0;
      border: none;
      
      .header-logo-img {
        height: 24px;
        width: auto;
        max-width: 100px;
        min-width: 24px;
        display: block;
        object-fit: contain;
        object-position: left center;
        background: transparent !important;
        background-color: transparent !important;
        filter: brightness(0) invert(1);
        opacity: 1;
        padding: 0;
        margin: 0;
        border: none;
        box-shadow: none;
      }
      
      .header-title {
        color: #ffffff;
        font-size: 16px;
        font-weight: 500;
        line-height: 24px;
        margin: 0;
        padding: 0;
      }
  }
  
  .close-btn {
    width: 32px;
    height: 32px;
    min-width: 32px;
    background: transparent;
    border: none;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    margin: 0;
    border-radius: 50%;
    transition: background-color 0.2s ease;
    flex-shrink: 0;
    
    .close-icon {
      width: 20px;
      height: 20px;
      color: #ffffff;
      display: block;
      flex-shrink: 0;
    }
    
    &:hover {
      background: rgba(255, 255, 255, 0.2);
    }
    
    &:active {
      background: rgba(255, 255, 255, 0.3);
    }
  }
}

.chatbot-messages {
  flex: 1;
  overflow-y: auto;
  background: rgb(var(--v-theme-basepage));
  padding: 20px 16px;
  
  .message {
    display: flex;
    margin-bottom: 16px;
    gap: 8px;
    
    &.user {
      flex-direction: row-reverse;
      margin-right: 12px;
      
      .message-wrapper {
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        max-width: 80%;
        margin-right: 0;
      }
      
      .message-content {
        display: inline-block;
        background: #c90000;
        color: white;
        padding: 12px 16px;
        border-radius: 18px;
        text-align: left;
        margin-right: 0;
      }
    }
    
    &.assistant {
      margin-left: 12px;
      
      .message-wrapper {
        display: flex;
        flex-direction: column;
        max-width: 80%;
      }
      
      .message-content {
        display: inline-block;
        background: rgb(var(--v-theme-surface));
        color: rgb(var(--v-theme-on-surface));
        padding: 12px 16px;
        border-radius: 12px;
        border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
        
        :deep(code) {
          background: rgba(var(--v-theme-on-surface), 0.1);
          padding: 2px 4px;
          border-radius: 4px;
          font-family: monospace;
        }
      }
      
      .message-timestamp {
        font-size: 11px;
        color: rgba(var(--v-theme-on-surface), 0.6);
        margin-top: 4px;
        margin-left: 4px;
      }
      
      .table-container {
        background: rgb(var(--v-theme-surface));
        border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
        border-radius: 8px;
        overflow-x: auto;
        overflow-y: visible;
        margin-top: 4px;
        max-width: 100%;
        width: 100%;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        scrollbar-width: thin;
        scrollbar-color: rgba(var(--v-theme-on-surface), 0.3) rgba(var(--v-theme-on-surface), 0.05);
        
        &::-webkit-scrollbar {
          height: 8px;
        }
        
        &::-webkit-scrollbar-track {
          background: rgba(var(--v-theme-on-surface), 0.05);
          border-radius: 4px;
        }
        
        &::-webkit-scrollbar-thumb {
          background: rgba(var(--v-theme-on-surface), 0.3);
          border-radius: 4px;
          
          &:hover {
            background: rgba(var(--v-theme-on-surface), 0.5);
          }
        }
        
        .table-title {
          padding: 12px 16px;
          background: rgb(var(--v-theme-basepage));
          font-weight: 600;
          font-size: 14px;
          color: rgb(var(--v-theme-on-surface));
          border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
        }
        
        .data-table {
          width: 100%;
          min-width: max-content;
          border-collapse: collapse;
          font-size: 13px;
          background: rgb(var(--v-theme-surface));
          
          thead {
            background: rgb(var(--v-theme-basepage));
            
            th {
              padding: 12px 16px;
              text-align: left;
              font-weight: 600;
              color: rgb(var(--v-theme-on-surface));
              border-bottom: 2px solid rgba(var(--v-theme-on-surface), 0.12);
              white-space: nowrap;
            }
          }
          
          tbody {
            background: rgb(var(--v-theme-surface));
            
            tr {
              border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
              
              &:hover {
                background: rgb(var(--v-theme-basepage));
              }
              
              &:last-child {
                border-bottom: none;
              }
            }
            
            td {
              padding: 12px 16px;
              color: rgb(var(--v-theme-on-surface));
              max-width: 300px;
              word-wrap: break-word;
              vertical-align: top;
              line-height: 1.5;
              white-space: nowrap;
            }
          }
        }
        
        .table-more {
          padding: 10px 16px;
          background: rgb(var(--v-theme-basepage));
          font-size: 12px;
          color: rgba(var(--v-theme-on-surface), 0.6);
          text-align: center;
          border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
        }
      }
      
    }
  }
  
  .loading-indicator {
    .typing-indicator {
    display: flex;
      gap: 4px;
      padding: 10px 14px;
      background: rgb(var(--v-theme-surface));
      border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
      border-radius: 12px;
      width: fit-content;
      
      span {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: rgba(var(--v-theme-on-surface), 0.6);
        opacity: 0.6;
        animation: typing 1.4s infinite;
        
        &:nth-child(2) {
          animation-delay: 0.2s;
        }
        
        &:nth-child(3) {
          animation-delay: 0.4s;
        }
      }
    }
  }
  
  @keyframes typing {
    0%, 60%, 100% {
      transform: translateY(0);
      opacity: 0.6;
    }
    30% {
      transform: translateY(-10px);
      opacity: 1;
    }
  }
}

.chatbot-input {
  border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  background: rgb(var(--v-theme-surface));
  padding: 12px 16px;
  
  .input-wrapper {
    display: flex;
    width: 100%;
    gap: 8px;
    align-items: center;
  }
  
  .file-input-hidden {
    display: none;
  }
  
  .attach-btn {
    width: 40px;
    height: 40px;
    min-width: 40px;
    background: transparent;
    border: none;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    margin: 0;
    border-radius: 8px;
    transition: background-color 0.2s ease;
    flex-shrink: 0;
    
    .attach-icon {
      width: 20px;
      height: 20px;
      color: rgba(var(--v-theme-on-surface), 0.7);
      display: block;
    }
    
    &:hover:not(:disabled) {
      background: rgba(var(--v-theme-on-surface), 0.05);
    }
    
    &:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
  }
  
  .message-input {
    flex: 1;
    
    :deep(.v-field) {
      border-radius: 8px;
      border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
      background: rgb(var(--v-theme-surface));
    }
    
    :deep(.v-field__input) {
      padding: 10px 16px;
      color: rgb(var(--v-theme-on-surface));
    }
    
    :deep(.v-field__outline) {
      border-color: rgba(var(--v-theme-on-surface), 0.12);
    }
    
    :deep(input::placeholder) {
      color: rgba(var(--v-theme-on-surface), 0.5);
    }
  }
  
  .send-btn {
    flex-shrink: 0;
    width: 40px;
    height: 40px;
    border-radius: 8px;
    background: #9e9e9e;
    color: #ffffff;
    min-width: 40px;
    border: none;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    transition: background-color 0.2s ease;
    
    .send-icon {
      width: 20px;
      height: 20px;
      color: #ffffff;
      display: block;
    }
    
    &:hover:not(:disabled) {
      background: #c90000;
    }
    
    &:disabled {
      opacity: 0.5;
      background: #e0e0e0;
      cursor: not-allowed;
      
      .send-icon {
        color: #757575;
      }
    }
  }
}

// Responsive design
@media (max-width: 600px) {
  .chatbot-window {
    width: calc(100vw - 40px);
    height: calc(100vh - 100px);
    max-width: 380px;
  }
  
  .chatbot-widget {
    bottom: 90px; /* Position above create button on mobile */
    right: 10px;
  }
}
</style>

<!-- Non-scoped styles for critical overrides that must not be affected by Vuetify -->
<style lang="scss">
.chatbot-widget {
  // Ensure toggle button icon is always white
  .chatbot-toggle svg.toggle-icon {
    fill: #ffffff !important;
    color: #ffffff !important;
  }
  
  // Ensure header logo container has no background
  .chatbot-header .header-logo {
    background: transparent !important;
    background-color: transparent !important;
    height: 24px !important;
    display: flex !important;
    align-items: center !important;
    width: auto !important;
    padding: 0 !important;
    margin: 0 !important;
    border: none !important;
    box-shadow: none !important;
    gap: 8px !important;
  }
  
  .chatbot-header .header-title {
    color: #ffffff !important;
    font-size: 16px !important;
    font-weight: 500 !important;
    line-height: 24px !important;
    margin: 0 !important;
    padding: 0 !important;
    visibility: visible !important;
    display: block !important;
  }
  
  .chatbot-header .header-logo-img {
    filter: brightness(0) invert(1) !important;
    opacity: 1 !important;
    visibility: visible !important;
    display: block !important;
    height: 24px !important;
    width: auto !important;
    max-width: 100px !important;
    min-width: 24px !important;
    background: transparent !important;
    background-color: transparent !important;
    object-fit: contain !important;
    object-position: left center !important;
    padding: 0 !important;
    margin: 0 !important;
    border: none !important;
    box-shadow: none !important;
  }
  
  // Ensure close button is always visible
  .chatbot-header .close-btn {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
  }
  
  .chatbot-header .close-btn .close-icon {
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
  }
  
  // Ensure header-left container has no background
  .chatbot-header .header-left {
    background: transparent !important;
  }
  
  // Ensure close button icon is always white
  .chatbot-header .close-btn svg.close-icon {
    fill: #ffffff !important;
    color: #ffffff !important;
  }
  
  // Ensure send button icon is always white
  .send-btn svg.send-icon {
    fill: #ffffff !important;
    color: #ffffff !important;
  }
  
  // Ensure header background is always red
  .chatbot-header {
    background-color: #c90000 !important;
  }
  
  // Ensure toggle button background is always red
  .chatbot-toggle {
    background-color: #c90000 !important;
  }
}
</style>
