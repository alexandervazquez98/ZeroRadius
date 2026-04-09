FROM rsyslog/rsyslog:latest

RUN apt-get update && apt-get install -y \
    rsyslog-omhttp \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY rsyslog.conf /etc/rsyslog.conf

EXPOSE 514/udp

# Run without -n so rsyslog logs to stdout automatically
CMD ["rsyslogd"]