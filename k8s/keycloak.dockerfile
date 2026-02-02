FROM quay.io/keycloak/keycloak:latest

# Pre-build for PostgreSQL; use /auth so app config (VEO_OIDC_URL with /auth) works (Quarkus default is no /auth)
RUN /opt/keycloak/bin/kc.sh build --db=postgres --http-relative-path=/auth

# Cap JVM heap for Render instance; bind to all interfaces
ENV JAVA_OPTS_APPEND="-Xmx256m -Xms128m -Dquarkus.http.host=0.0.0.0"
ENV KC_HTTP_PORT=8080
ENV KC_HOSTNAME_STRICT=false
# Production behind edge proxy: HTTP only (TLS at Render); parse X-Forwarded-* headers
ENV KC_HTTP_ENABLED=true
ENV KC_PROXY_HEADERS=xforwarded

# Production start with optimized build; hostname set via env (e.g. sparksbm-auth.onrender.com)
ENTRYPOINT ["/opt/keycloak/bin/kc.sh", "start", "--optimized"]