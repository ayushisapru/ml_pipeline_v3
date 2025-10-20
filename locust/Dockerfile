FROM locustio/locust:latest

WORKDIR /mnt/locust

# Copy test scenarios and ancillary files into the image
COPY . /mnt/locust

# Install any additional Python requirements (if the file is empty this is a no-op)
RUN if [ -f /mnt/locust/requirements.txt ]; then pip install --no-cache-dir -r /mnt/locust/requirements.txt || true; fi

# Default command keeps the upstream entrypoint behavior; expose nothing additional here
CMD ["locust"]
