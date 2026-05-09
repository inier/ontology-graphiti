FROM localhost/node:20-alpine AS builder

WORKDIR /app

COPY package.json ./
RUN npm install --registry https://registry.npmmirror.com

COPY . .
RUN npm run build

FROM localhost/nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY <<'EOF' /etc/nginx/conf.d/default.conf
server {
    listen 80;
    server_name localhost;

    location / {
        root /usr/share/nginx/html;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://graphiti-main-app:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_buffering off;
    }

    location /health {
        proxy_pass http://graphiti-main-app:8000;
    }
}
EOF

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
