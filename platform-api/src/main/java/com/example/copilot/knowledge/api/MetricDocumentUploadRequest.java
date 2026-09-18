package com.example.copilot.knowledge.api;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record MetricDocumentUploadRequest(
        @NotBlank @Size(max = 240) String title,
        @NotBlank @Size(max = 255) String sourceName,
        @Pattern(regexp = "MARKDOWN|PDF") String sourceType,
        @NotBlank @Size(max = 14_000_000) String contentBase64) {}
