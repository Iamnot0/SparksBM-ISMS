FROM quay.io/keycloak/keycloak:latest

# Stay within Render free-tier 512Mi: cap JVM heap so the process doesn't OOM before opening the port
ENV JAVA_OPTS_APPEND="-Xmx256m -Xms128m"
# Ensure HTTP is on 8080 and bound to all interfaces (Render probes this port)
ENV KC_HTTP_PORT=8080
ENV KC_HOSTNAME_STRICT=false

ENTRYPOINT ["/opt/keycloak/bin/kc.sh", "start-dev"]