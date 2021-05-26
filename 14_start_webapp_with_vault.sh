#!/bin/sh
docker stop vault-demo-webapp
docker rm vault-demo-webapp

cd backend
#rebuild the webapp container and start
docker build -t pcoca/vault-demo-webapp:latest .
docker run --detach --name vault-demo-webapp --network dev-network -p 5000:5000 pcoca/vault-demo-webapp:latest