FROM localhost/node:20-alpine AS builder

WORKDIR /app

COPY package.json ./
RUN npm install --registry https://registry.npmmirror.com

COPY . .
RUN node ./node_modules/vite/bin/vite.js build

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
}
EOF

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
