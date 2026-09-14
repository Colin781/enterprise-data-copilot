package com.example.copilot.security;

import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "platform.security")
public record SecurityProperties(String jwtSecret, String jwtIssuer, Duration accessTokenTtl) {
    public SecurityProperties {
        if (jwtSecret == null || jwtSecret.getBytes(java.nio.charset.StandardCharsets.UTF_8).length < 32) {
            throw new IllegalArgumentException("platform.security.jwt-secret must be at least 32 bytes");
        }
        if (jwtIssuer == null || jwtIssuer.isBlank()) {
            throw new IllegalArgumentException("platform.security.jwt-issuer is required");
        }
        if (accessTokenTtl == null || accessTokenTtl.isNegative() || accessTokenTtl.isZero()) {
            throw new IllegalArgumentException("platform.security.access-token-ttl must be positive");
        }
    }
}
