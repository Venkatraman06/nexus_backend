docker exec keycloak /opt/keycloak/bin/kcadm.sh create realms -s realm=pmt -s enabled=true
docker exec keycloak /opt/keycloak/bin/kcadm.sh create clients -r pmt -s clientId=pmt-client -s enabled=true -s publicClient=false -s secret=secret -s directAccessGrantsEnabled=true
docker exec keycloak /opt/keycloak/bin/kcadm.sh create users -r pmt -s username=ceo@hackersinfotech.com -s enabled=true
docker exec keycloak /opt/keycloak/bin/kcadm.sh set-password -r pmt --username ceo@hackersinfotech.com --new-password password123
docker exec keycloak /opt/keycloak/bin/kcadm.sh create users -r pmt -s username=hit-001 -s enabled=true
docker exec keycloak /opt/keycloak/bin/kcadm.sh set-password -r pmt --username hit-001 --new-password password123
