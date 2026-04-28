FROM node:20-alpine AS build
WORKDIR /app
COPY services/ui/package.json .
RUN npm install
COPY services/ui/ .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY services/ui/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
