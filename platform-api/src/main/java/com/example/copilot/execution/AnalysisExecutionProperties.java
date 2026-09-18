package com.example.copilot.execution;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

@Validated
@ConfigurationProperties("platform.execution")
public record AnalysisExecutionProperties(
        boolean enabled,
        @Min(1) @Max(32) int corePoolSize,
        @Min(1) @Max(64) int maxPoolSize,
        @Min(1) @Max(10_000) int queueCapacity,
        @Min(1) @Max(5) int maxAttempts,
        @NotNull Duration retryBackoff,
        @NotNull Duration eventRetention,
        @Min(10) @Max(10_000) int eventMaxLength,
        @NotNull Duration sseTimeout,
        @NotNull Duration dispatchLease) {

    public AnalysisExecutionProperties {
        if (maxPoolSize < corePoolSize) {
            throw new IllegalArgumentException("maxPoolSize must be greater than or equal to corePoolSize");
        }
        if (retryBackoff.isNegative()
                || eventRetention.isNegative()
                || eventRetention.isZero()
                || sseTimeout.isNegative()
                || sseTimeout.isZero()
                || dispatchLease.isNegative()
                || dispatchLease.isZero()) {
            throw new IllegalArgumentException("execution durations must be positive, except retryBackoff may be zero");
        }
    }
}
