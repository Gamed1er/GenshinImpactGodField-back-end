FROM python:3.10-slim

# 讓 Python Log 即時輸出到控制台
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 習慣上會宣告容器要使用的 Port，雖然這只是提示作用
EXPOSE 65432

CMD ["python", "main.py"]