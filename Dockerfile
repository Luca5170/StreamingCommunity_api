# SC Downloader

FROM python:3.11-slim

# ffmpeg joins the segments of the video, the rest is needed by the site requests
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY Src ./Src
COPY gui.py run.py ./

# Everything the program writes (videos, downloads to resume, settings, history) stays here
WORKDIR /data
VOLUME ["/data"]

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    TZ=Europe/Rome

# The app answers on this port to every device of the home network
EXPOSE 8770

HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8770/api/status', timeout=8)"

CMD ["python", "/app/gui.py", "--no-window"]
