FROM python:3.13-slim


ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app


RUN apt-get update && apt-get install -y build-essential \
    && rm -rf /var/lib/apt/lists/*


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


COPY . .


RUN python manage.py collectstatic --noinput


EXPOSE 7860


CMD ["gunicorn", "myproject.wsgi:application", "--bind", "0.0.0.0:7860"]
