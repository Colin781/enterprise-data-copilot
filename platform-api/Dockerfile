FROM eclipse-temurin:21-jdk-jammy AS build
WORKDIR /workspace
COPY .mvn .mvn
COPY mvnw pom.xml ./
RUN ./mvnw --batch-mode -DskipTests dependency:go-offline
COPY src src
RUN ./mvnw --batch-mode -DskipTests package

FROM eclipse-temurin:21-jre-jammy
WORKDIR /app
COPY --from=build /workspace/target/platform-api-0.0.1-SNAPSHOT.jar app.jar
EXPOSE 8080
USER 10001:10001
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75", "-jar", "/app/app.jar"]
