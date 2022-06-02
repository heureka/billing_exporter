FROM python:3.10.4-slim

ADD ./requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

ADD . /app

WORKDIR /app

ENTRYPOINT ["python", "main.py"]
