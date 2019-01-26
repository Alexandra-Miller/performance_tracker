#!/bin/bash
# Always execute this file with this directory as CWD

if [ $# -eq 0 ]
  then
    echo "Please provide your username as argument"
    exit 1
fi

bash ./query_schedule.sh $1

docker run \
  -u $(id -u $1):$(id -g $1) \
  --rm \
  -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
  -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
  -v $(pwd):/src metro python upload_schedule.py
if [ $? -eq 0 ]; then
  echo "Successfully uploaded schedule to S3:" $(date) >> $(pwd)/logs/uploadLog
else
  echo "Failed S3 upload:" $(date) >> $(pwd)/logs/uploadLog
  exit 1
fi