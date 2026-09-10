FROM python:3.11-slim

WORKDIR /app

COPY services/model/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/model/app/ ./app/
COPY models/ ./models/

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
