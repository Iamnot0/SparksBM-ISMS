FROM quay.io/keycloak/keycloak:latest

# Pre-build for PostgreSQL so runtime uses start --optimized (no Quarkus augmentation; much faster startup)
RUN /opt/keycloak/bin/kc.sh build --db=postgres

# Cap JVM heap for Render instance; bind to all interfaces
ENV JAVA_OPTS_APPEND="-Xmx256m -Xms128m -Dquarkus.http.host=0.0.0.0"
ENV KC_HTTP_PORT=8080
ENV KC_HOSTNAME_STRICT=false
# Production behind edge proxy: HTTP only (TLS at Render); parse X-Forwarded-* headers
ENV KC_HTTP_ENABLED=true
ENV KC_PROXY_HEADERS=xforwarded

# Production start with optimized build; hostname set via env (e.g. sparksbm-auth.onrender.com)
ENTRYPOINT ["/opt/keycloak/bin/kc.sh", "start", "--optimized"]