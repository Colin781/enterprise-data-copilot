package com.example.copilot.integration.agent;

import jakarta.validation.constraints.NotBlank;
import java.net.URI;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

@Validated
@ConfigurationProperties("platform.agent")
public record AgentIntegrationProperties(@NotBlank String serviceToken, URI baseUrl) {}
