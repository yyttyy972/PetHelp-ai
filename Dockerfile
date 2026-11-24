FROM node:22-alpine AS frontend
WORKDIR /app/frontend-html
COPY frontend-html/package*.json ./
RUN npm ci
COPY frontend-html/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_ENV=production
WORKDIR /app
COPY backend/requirements.txt backend/requirements-ai.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt -r backend/requirements-ai.txt
COPY backend/ ./backend/
COPY --from=frontend /app/frontend-html/dist ./frontend-html/dist
WORKDIR /app/backend
CMD ["python", "scripts/start_render.py"]
