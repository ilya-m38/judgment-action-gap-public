FROM python:3.12-alpine
WORKDIR /opt/desk-service
COPY service.py /opt/desk-service/service.py
COPY operations.py /opt/desk-service/operations.py
USER 10001:10001
ENTRYPOINT ["python3", "/opt/desk-service/service.py"]
