FROM quay.io/keycloak/keycloak:latest
ENTRYPOINT ["/opt/keycloak/bin/kc.sh", "start-dev"]