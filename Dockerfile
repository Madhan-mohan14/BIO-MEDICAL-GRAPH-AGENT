FROM node:20-slim AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS python-builder
WORKDIR /app
RUN pip install uv
# Install CPU-only torch first — avoids pulling 2GB of NVIDIA CUDA packages.
# Cloud Run is CPU-only; the default torch wheel bundles full CUDA.
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

# Pre-download sentence-transformer models so Cloud Run cold starts don't stall.
# all-mpnet-base-v2: ~420MB (semantic search + embedding)
# cross-encoder/ms-marco-MiniLM-L-6-v2: ~85MB (cross-encoder reranker)
RUN python -c "\
from sentence_transformers import SentenceTransformer, CrossEncoder; \
SentenceTransformer('all-mpnet-base-v2'); \
CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

FROM python:3.11-slim
WORKDIR /app
COPY --from=python-builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=python-builder /usr/local/bin /usr/local/bin
# Copy cached HuggingFace models from builder so they're baked into the image
COPY --from=python-builder /root/.cache/huggingface /root/.cache/huggingface
COPY . .
# Copy the built React frontend so FastAPI can serve it as static files
COPY --from=frontend-builder /frontend/dist ./frontend/dist
ENV PORT=8080
EXPOSE 8080
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
