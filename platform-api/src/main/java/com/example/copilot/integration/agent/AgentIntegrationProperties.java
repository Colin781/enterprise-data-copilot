package com.example.copilot.integration.agent;

import jakarta.validation.constraints.NotBlank;
import java.net.URI;
import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

@Validated
@ConfigurationProperties("platform.agent")
public record AgentIntegrationProperties(
        @NotBlank String serviceToken, URI baseUrl, Duration connectTimeout, Duration requestTimeout) {

    public AgentIntegrationProperties {
        if (baseUrl == null) {
            throw new IllegalArgumentException("baseUrl is required");
        }
        if (connectTimeout == null || connectTimeout.isZero() || connectTimeout.isNegative()) {
            throw new IllegalArgumentException("connectTimeout must be positive");
        }
        if (requestTimeout == null || requestTimeout.isZero() || requestTimeout.isNegative()) {
            throw new IllegalArgumentException("requestTimeout must be positive");
        }
    }
}
