FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY onionplane ./onionplane

# SQLite lives on a mounted volume so services + keys survive restarts.
ENV ONIONPLANE_DB=/data/onionplane.db
EXPOSE 8000

CMD ["uvicorn", "onionplane.main:app", "--host", "0.0.0.0", "--port", "8000"]
