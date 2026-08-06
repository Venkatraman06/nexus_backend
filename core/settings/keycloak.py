from decouple import config

KEYCLOAK_SERVER_URL = config("KEYCLOAK_SERVER_URL", default="http://localhost:8080/")
KEYCLOAK_CLIENT_ID = config("KEYCLOAK_CLIENT_ID", default="pmt-backend")
KEYCLOAK_CLIENT_SECRET_KEY = config("KEYCLOAK_CLIENT_SECRET_KEY", default="nPp2QuUFmrm70tcCXDRwqupFhZTXVI0em5pLNLcNbVY=")
KEYCLOAK_REALM = config("KEYCLOAK_REALM", default="pmt")
KEYCLOAK_TOKEN_CLIENT_ID = config("KEYCLOAK_TOKEN_CLIENT_ID", default="pmt-frontend")

# Realm-role attribute ``product`` used to scope permissions for this app (IAM model).
PMT_PERMISSION_PRODUCT = config("PMT_PERMISSION_PRODUCT", default="pmt")
PMT_PERMISSIONS_CACHE_TTL = config("PMT_PERMISSIONS_CACHE_TTL", default=300, cast=int)
