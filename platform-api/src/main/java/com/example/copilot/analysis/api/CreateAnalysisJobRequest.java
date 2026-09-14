package com.example.copilot.analysis.api;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.util.UUID;

public record CreateAnalysisJobRequest(@NotNull UUID dataSourceId, @NotBlank @Size(max = 4000) String question) {}
