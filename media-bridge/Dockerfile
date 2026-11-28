FROM python:3.13-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY service.py entrypoint.py test_service.py /app/

RUN python3 -m py_compile service.py entrypoint.py test_service.py \
    && python3 -m unittest -v

EXPOSE 8090

ENTRYPOINT ["python3", "-u", "/app/entrypoint.py"]
