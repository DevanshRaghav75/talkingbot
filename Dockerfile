FROM python:3

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py .

CMD [ "python", "./bot.py", "--config-file=/config/config.yaml" ]
