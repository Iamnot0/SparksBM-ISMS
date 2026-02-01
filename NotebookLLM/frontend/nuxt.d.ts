// Nuxt auto-imports type definitions
export {}

declare global {
  const useRuntimeConfig: () => {
    public: {
      apiBase: string
    }
  }
  
  const $fetch: <T = any>(
    url: string,
    options?: {
      method?: string
      params?: Record<string, any>
      body?: any
      signal?: AbortSignal
    }
  ) => Promise<T>
  
  const defineNuxtConfig: (config: any) => any
  const defineNuxtPlugin: (plugin: any) => any
}
