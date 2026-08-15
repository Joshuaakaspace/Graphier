# --- frontend build ---
FROM node:20-slim AS frontend
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- runtime ---
FROM python:3.12-slim
# git powers vault snapshots / time travel
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
# Lean install: pattern extraction + reasoning, no ML downloads
RUN pip install --no-cache-dir --no-deps semantica \
    && pip install --no-cache-dir numpy pandas scipy networkx pypdf \
       python-multipart fastapi "uvicorn[standard]"

COPY backend/ backend/
COPY --from=frontend /app/dist frontend/dist

ENV GRAPHIER_VAULT=/vault \
    GRAPHIER_HOST=0.0.0.0 \
    GRAPHIER_PORT=8000 \
    SEMANTICA_DISABLE_PROGRESS=1
VOLUME /vault
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "graphier.main:create_app", "--factory", \
     "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
