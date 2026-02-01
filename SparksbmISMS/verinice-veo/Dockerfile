FROM gradle:8.5-jdk21-alpine AS builder

WORKDIR /home/gradle/src

COPY --chown=gradle:gradle . .

# Build the application
# Using 'bootJar' assuming the spring boot plugin is applied to the runnable module (likely veo-rest or similar)
# If the root build.gradle applies it to subprojects, we need to find the jar.
RUN ./gradlew bootJar --no-daemon

FROM eclipse-temurin:21-jre-alpine

WORKDIR /app

# We need to identify the correct jar. Assuming it's in veo-rest or root build/libs
# We'll use a wildcard copy for robustness in this template
COPY --from=builder /home/gradle/src/veo-rest/build/libs/*.jar app.jar

EXPOSE 8080

# Limit heap to 350m to fit in 512MB free tier containers (Render/Koyeb)
ENV JAVA_TOOL_OPTIONS="-Xmx350m -Xms350m"

ENTRYPOINT ["java", "-jar", "app.jar"]