FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev git && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml constraints.txt ./
RUN pip install --no-cache-dir -c constraints.txt -e . && \
    pip install --no-cache-dir -c constraints.txt \
      "git+https://github.com/Kotak-Neo/Kotak-neo-api-v2.git@v2.0.2#egg=neo_api_client" || true && \
    pip install --no-cache-dir -c constraints.txt --force-reinstall "websockets>=12.0,<14.0" && \
    python -c "import uvicorn.config as c; from uvicorn.importer import import_from_string; import_from_string(c.WS_PROTOCOLS['websockets-sansio']); print('uvicorn ws ok')"

COPY . .

RUN chmod +x docker-entrypoint.sh

ENTRYPOINT ["./docker-entrypoint.sh"]
# websockets-sansio avoids websockets.legacy (removed in websockets 15+)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--ws", "websockets-sansio"]
