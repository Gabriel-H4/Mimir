# First Stage: Install dependencies
FROM python:3.11-alpine AS builder

COPY requirements.txt .
RUN pip install --user -r requirements.txt


# Second Stage: Add Code and Run App
FROM python:3.11-alpine
WORKDIR /mimir

COPY . .
COPY --from=builder /root/.local /root/.local

# Update PATH environment variable
ENV PATH=/root/.local:$PATH

EXPOSE 80/tcp

ENTRYPOINT [ "/mimir/gunicorn.sh", "-w 4", "mimir" ]

HEALTHCHECK --interval=30s --timeout=30s --start-period=15s --retries=3 CMD [ "curl -f http://localhost/ || exit 1" ]
