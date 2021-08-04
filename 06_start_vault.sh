#!/bin/sh
#stop and remove vault containers if already running
docker stop vault-demo-vault
docker rm vault-demo-vault
#start Vault in dev mode on port 8200
docker run --detach --name vault-demo-vault --network dev-network -p 8200:8200 -e VAULT_LICENSE=$(cat ./license.txt) hashicorp/vault-enterprise:1.8.0_ent server -dev -dev-root-token-id="root"
