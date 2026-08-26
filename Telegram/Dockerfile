FROM node:24-slim AS build
WORKDIR /workspace
COPY package.json package-lock.json* ./
RUN npm install
COPY tsconfig.json ./
COPY src src
RUN npm run build

FROM node:24-slim
WORKDIR /workspace
COPY package.json package-lock.json* ./
RUN npm install --omit=dev
COPY --from=build /workspace/dist dist
CMD ["node", "--env-file-if-exists=.env", "dist/index.js"]
