# select base image
FROM python:3.10-slim

# workdir inside the container is /app
WORKDIR /app

# install git in order to use setuptools_scm
# required for automatic detection of version
RUN apt-get update && apt-get install -y git

# copy everything into container
COPY . .

# run installation inside the container
RUN pip install --no-cache-dir .
RUN rm -rf .git
RUN rm -rf .github

# ready - run the realtime observer
ENTRYPOINT ["python"]
CMD ["-m", "realtimeobserver", "observe", "/app/data/data.db3", "/app/config/config.yaml"]
