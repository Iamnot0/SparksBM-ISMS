FROM quay.io/keycloak/keycloak:latest

# Pre-build for PostgreSQL so runtime uses start --optimized (no Quarkus augmentation; much faster startup)
RUN /opt/keycloak/bin/kc.sh build --db=postgres

# Cap JVM heap for Render instance
ENV JAVA_OPTS_APPEND="-Xmx256m -Xms128m -Dquarkus.http.host=0.0.0.0"
ENV KC_HTTP_PORT=8080
ENV KC_HOSTNAME_STRICT=false

# Production start with optimized build; HTTP/hostname/proxy set via env at runtime
ENTRYPOINT ["/opt/keycloak/bin/kc.sh", "start", "--optimized"]