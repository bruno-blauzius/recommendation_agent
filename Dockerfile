FROM python:3.12

RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

RUN PYTHONUNBUFFERED=1

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

CMD [ "python", "main.py" ]
