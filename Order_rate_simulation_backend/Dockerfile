# 1. Gunakan Python ≥ 3.10 untuk kompatibilitas dependency
FROM python:3.10-slim

# 2. Set working directory
WORKDIR /app

# 3. Salin requirements dan upgrade pip
COPY requirements.txt ./
RUN pip install --upgrade pip

# 4. Install curl via apt-get
#    - update + install dalam satu layer
#    - --no-install-recommends untuk mencegah paket tak perlu
#    - hapus cache apt setelah install
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# 5. Install Python dependencies
RUN pip install -r requirements.txt

# 6. Salin sisa kode aplikasi
COPY . .

# 7. Buka port aplikasi
EXPOSE 5002

# 8. Jalankan aplikasi
CMD ["python", "server.py"]
