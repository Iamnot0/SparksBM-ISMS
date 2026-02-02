FROM node:20-alpine AS builder

WORKDIR /app

# Backend API URL baked at build time (set in Render env or: docker build --build-arg API_BASE_URL=https://...)
ARG API_BASE_URL=http://localhost:8000
ENV API_BASE_URL=${API_BASE_URL}
ENV API_URL=${API_BASE_URL}

COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

FROM node:20-alpine

WORKDIR /app

COPY --from=builder /app/.output ./.output
COPY --from=builder /app/package*.json ./

ENV HOST=0.0.0.0
ENV PORT=3000

EXPOSE 3000

CMD ["node", ".output/server/index.mjs"]