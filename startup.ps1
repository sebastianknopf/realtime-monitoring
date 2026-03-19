docker run --rm `
  -v "${PWD}\config\dev.yaml:/app/config/config.yaml" `
  -v "${PWD}\sampledata\realtimeobserver.db3:/app/data/data.db3" `
  sebastianknopf/realtimeobserver:latest