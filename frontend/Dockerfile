FROM node:20-alpine AS build

WORKDIR /app/frontend

ARG REACT_APP_BACKEND_URL=http://localhost:8001
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL
ENV WDS_SOCKET_PORT=0

COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile

COPY . .
RUN yarn build

# --- Serveur statique ---
FROM node:20-alpine
WORKDIR /app
RUN yarn global add serve
COPY --from=build /app/frontend/build ./build
EXPOSE 3000
CMD ["serve", "-s", "build", "-l", "3000"]
