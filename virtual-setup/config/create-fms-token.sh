#!/bin/sh

set -e

token=$(influx auth create \
  --hide-headers \
  --description "Token for writing to the FMS demo bucket" \
  --user "${DOCKER_INFLUXDB_INIT_USERNAME}" \
  --read-bucket "${DOCKER_INFLUXDB_INIT_BUCKET_ID}" \
  --write-bucket "${DOCKER_INFLUXDB_INIT_BUCKET_ID}" | awk -F '\t' '{print $3}')

echo "${token}" > /tmp/out/fms-demo.token

cat <<EOF > /tmp/influxdb-datasources/influxdb.yaml
apiVersion: 1
datasources:
- name: "InfluxDB-SDV-Flux"
  uid: "PDC312342D5DCA611"
  type: influxdb
  access: proxy
  url: http://influxdb:8086
  jsonData:
    version: Flux
    organization: ${DOCKER_INFLUXDB_INIT_ORG}
    defaultBucket: ${DOCKER_INFLUXDB_INIT_BUCKET}
    tlsSkipVerify: true
  secureJsonData:
    token: ${token}
EOF
