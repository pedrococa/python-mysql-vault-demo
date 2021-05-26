export VAULT_ADDR=http://localhost:8200
export VAULT_TOKEN=root
export VAULT_NAMESPACE=dev

#enable the transform secret engine
vault secrets enable -path=tokenization_protection/transform transform

#Define a role payment with transformation payment 
vault write tokenization_protection/transform/role/payment transformations=credit-card

#create a transformation using built in template for credit-card and assign role payment to it that we created earlier
vault write tokenization_protection/transform/transformations/tokenization/credit-card allowed_roles=payment max_ttl=24h
#test if the transformation was created successfully
vault list tokenization_protection/transform/transformations/tokenization
vault read tokenization_protection/transform/transformations/tokenization/credit-card
#test if you are able to tokenize the credit card number
vault write tokenization_protection/transform/encode/payment value=1111-2222-3333-4444 transformation=credit-card
vault write tokenization_protection/transform/encode/payment value=1111-2222-3333-4444 transformation=credit-card
vault write tokenization_protection/transform/encode/payment value=1111-2222-3333-4444 transformation=credit-card
