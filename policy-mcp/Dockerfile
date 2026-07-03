FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY policy_server.py .

EXPOSE 8001

CMD ["python", "policy_server.py"]
