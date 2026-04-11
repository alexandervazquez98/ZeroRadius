FROM python:3.11-slim

RUN pip install --no-cache-dir requests

COPY syslog-forwarder.py /usr/local/bin/syslog-forwarder.py
RUN chmod +x /usr/local/bin/syslog-forwarder.py

EXPOSE 514/udp

CMD ["python", "/usr/local/bin/syslog-forwarder.py"]