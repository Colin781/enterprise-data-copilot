package com.example.copilot.analysis.api;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import java.util.Map;

public record RecordAgentStepRequest(
        @NotBlank @Size(max = 80) String stepName,
        @NotBlank @Pattern(regexp = "SUCCEEDED|FAILED|WAITING") String status,
        @Min(0) @Max(3) int attempt,
        @NotNull Map<String, Object> inputSummary,
        @NotNull Map<String, Object> outputSummary,
        @Min(0) long durationMs,
        @Size(max = 80) String errorCode) {}
