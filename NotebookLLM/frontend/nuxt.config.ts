export default defineNuxtConfig({
  ssr: false,
  devServer: {
    port: parseInt(process.env.FRONTEND_PORT || '3002'),
    host: process.env.FRONTEND_HOST || 'localhost'
  },
  css: ['vuetify/styles'],
  build: {
    transpile: ['vuetify']
  },
  vite: {
    define: {
      'process.env.DEBUG': false
    }
  },
  runtimeConfig: {
    public: {
      apiBase: process.env.API_BASE_URL || process.env.API_URL || 'http://localhost:8000'
    }
  }
})
