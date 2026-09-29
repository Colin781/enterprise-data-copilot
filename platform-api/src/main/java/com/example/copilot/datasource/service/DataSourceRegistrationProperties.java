package com.example.copilot.datasource.service;

import com.example.copilot.datasource.api.CreateDataSourceRequest;
import com.example.copilot.datasource.domain.DataSource;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import java.util.Locale;
import java.util.Set;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

@Validated
@ConfigurationProperties("platform.data-source-registration")
public record DataSourceRegistrationProperties(
        @NotEmpty Set<String> allowedHosts,
        @NotBlank String demoHost,
        @Min(1) @Max(65535) int demoPort,
        @NotBlank String demoDatabaseName,
        @NotBlank String demoAllowedSchema,
        @NotBlank String demoSecretRef) {

    public boolean allows(String host) {
        var normalized = host.trim().toLowerCase(Locale.ROOT);
        return allowedHosts.stream()
                .map(value -> value.trim().toLowerCase(Locale.ROOT))
                .anyMatch(normalized::equals);
    }

    public boolean matches(CreateDataSourceRequest request) {
        return matches(
                request.host(), request.port(), request.databaseName(), request.allowedSchema(), request.secretRef());
    }

    public boolean matches(DataSource source) {
        return source.isEnabled()
                && matches(
                        source.getHost(),
                        source.getPort(),
                        source.getDatabaseName(),
                        source.getAllowedSchema(),
                        source.getSecretRef());
    }

    private boolean matches(String host, int port, String database, String schema, String secretRef) {
        return host.trim().equalsIgnoreCase(demoHost.trim())
                && port == demoPort
                && database.trim().equals(demoDatabaseName.trim())
                && schema.trim().equals(demoAllowedSchema.trim())
                && secretRef.trim().equals(demoSecretRef.trim());
    }
}
