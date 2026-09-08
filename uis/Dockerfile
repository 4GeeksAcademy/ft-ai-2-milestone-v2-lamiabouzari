# syntax=docker/dockerfile:1.7
FROM node:22-alpine

WORKDIR /workspace

COPY --from=repository packages/shared ./packages/shared
COPY website/package.json website/package-lock.json ./uis/website/
COPY backoffice/package.json backoffice/package-lock.json ./uis/backoffice/

RUN npm ci --prefix ./uis/website && npm ci --prefix ./uis/backoffice

COPY . ./uis

EXPOSE 3000 3001

CMD ["sh", "/workspace/uis/start.sh"]