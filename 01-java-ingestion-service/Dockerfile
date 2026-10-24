# Optimize for production deployment of a Java application using Maven and Eclipse Temurin JRE.
# This Dockerfile employs a multi-stage build to separate the compilation and runtime environments,
# using Maven for dependency management and Eclipse Temurin JRE for executing the application.
# The final image is based on a lightweight Alpine Linux distribution, and it runs the application as a non-root user to enhance security.
# Notice the use of caching strategies for Maven dependencies and the isolation of the build artifacts to minimize the final image size.
# Also notice the use of FROM ... AS ... multi-stage build.

# --- STAGE 1: Compilation Engine ---
FROM maven:3.9.6-eclipse-temurin-21-alpine AS compiler
WORKDIR /build

# Isolate pom.xml resolution to leverage caching layers
COPY pom.xml .
RUN mvn dependency:go-offline -B

# Copy structural codebase artifacts and execute production package build
COPY src ./src
RUN mvn clean package -DskipTests

# --- STAGE 2: Lightweight JRE Linux Runtime Execution ---
FROM eclipse-temurin:21-jre-alpine
WORKDIR /app

# Apply Alpine's security updates on top of the base image. The base image (eclipse-temurin:21-jre-alpine) is rebuilt
# by its maintainers only every few weeks; a fix published by Alpine in between (here brotli-libs, CVE-2026-111497)
# would otherwise fail image-scan until then. --no-cache: download the package index, use it, keep nothing.
RUN apk upgrade --no-cache

# Create a non-root user to run the application for security best practices
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

# Steal ONLY the compiled standalone portable JAR from the build stage
COPY --from=compiler /build/target/gateway.jar gateway.jar
RUN chown -R appuser:appgroup /app
USER appuser

# Define network routing target vectors
EXPOSE 8081

# Boot application cleanly using standard JVM flags
ENTRYPOINT ["java", "-jar", "gateway.jar"]
