FROM python:3.13-slim

WORKDIR /app

RUN adduser --system --no-create-home --group bot

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py /app/
COPY bot.py /app/
COPY main.py /app/
COPY virus_checker.py /app/
COPY leaks_aggregator.py /app/
COPY handlers /app/handlers
COPY services /app/services

RUN mkdir -p /app/logs && chown bot:bot /app/logs

USER bot

CMD ["python", "main.py"]