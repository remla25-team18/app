FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y git gcc build-essential

RUN pip install --upgrade pip setuptools wheel

WORKDIR /app

COPY . /app

RUN pip install -r requirements.txt

EXPOSE 4200

CMD ["python", "run.py"]
