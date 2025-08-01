FROM python:3.12-slim AS builder
WORKDIR /app
RUN pip install --upgrade pip
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Final Stage ---
FROM python:3.12-slim
WORKDIR /app
RUN addgroup --system app && adduser --system --group app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY . .
RUN chown -R app:app /app
USER app
CMD ["python", "main.py"] 