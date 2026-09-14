package com.example.copilot.datasource.api;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record CreateDataSourceRequest(
        @NotBlank @Size(max = 160) String name,
        @NotBlank @Size(max = 255) String host,
        @Min(1) @Max(65535) int port,
        @NotBlank @Size(max = 128) String databaseName,
        @NotBlank @Pattern(regexp = "[a-z_][a-z0-9_]*") @Size(max = 63) String allowedSchema,
        @NotBlank @Pattern(regexp = "(env|vault|secret):[A-Za-z0-9_./-]+") @Size(max = 255) String secretRef) {}
