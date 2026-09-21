package com.example.copilot.datasource.service;

import jakarta.validation.constraints.NotEmpty;
import java.util.Locale;
import java.util.Set;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

@Validated
@ConfigurationProperties("platform.data-source-registration")
public record DataSourceRegistrationProperties(@NotEmpty Set<String> allowedHosts) {

    public boolean allows(String host) {
        var normalized = host.trim().toLowerCase(Locale.ROOT);
        return allowedHosts.stream()
                .map(value -> value.trim().toLowerCase(Locale.ROOT))
                .anyMatch(normalized::equals);
    }
}
