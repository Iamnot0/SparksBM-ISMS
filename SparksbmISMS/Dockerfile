FROM gradle:8.5-jdk21-alpine AS builder

WORKDIR /home/gradle/src

# Copy the submodule content (assuming GIT_STRATEGY=submodules worked)
COPY verinice-veo/ .

# Build the application
# Using 'bootJar' assuming the spring boot plugin is applied to the runnable module
RUN ./gradlew bootJar --no-daemon

FROM eclipse-temurin:21-jre-alpine

WORKDIR /app

# Copy the built jar
COPY --from=builder /home/gradle/src/veo-rest/build/libs/*.jar app.jar

EXPOSE 8080

ENTRYPOINT ["java", "-jar", "app.jar"]
