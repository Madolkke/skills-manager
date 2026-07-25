FROM node:24-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_SKILLHUB_EVALUATIONS_VISIBLE=true
ENV VITE_SKILLHUB_EVALUATIONS_VISIBLE=$VITE_SKILLHUB_EVALUATIONS_VISIBLE
RUN npm run build

FROM node:24-alpine
WORKDIR /app
RUN npm install -g serve
COPY --from=build /app/dist ./dist
EXPOSE 3030
CMD ["serve", "-s", "dist", "-l", "3030"]
