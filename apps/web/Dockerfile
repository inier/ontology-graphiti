FROM localhost/node-base:24 AS builder

WORKDIR /app

RUN corepack enable && corepack prepare pnpm@9 --activate

ARG VITE_API_BASE=

# 复制 workspace 配置 + 前端 package.json（层缓存友好）
COPY pnpm-workspace.yaml pnpm-lock.yaml .npmrc ./
COPY apps/web/package.json ./apps/web/

# 安装依赖（workspace 模式）
RUN pnpm install --frozen-lockfile || pnpm install

# 复制前端源码并构建
COPY apps/web ./apps/web
WORKDIR /app/apps/web
RUN node ./node_modules/vite/bin/vite.js build

FROM localhost/nginx:alpine
COPY --from=builder /app/apps/web/dist /usr/share/nginx/html
COPY <<'EOF' /etc/nginx/conf.d/default.conf
server {
    listen 80;
    server_name localhost;

    location /api/ {
        proxy_pass http://app:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    location /health {
        proxy_pass http://app:8000;
        proxy_set_header Host $host;
    }

    location / {
        root /usr/share/nginx/html;
        index index.html;
        try_files $uri $uri/ /index.html;
    }
}
EOF

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
