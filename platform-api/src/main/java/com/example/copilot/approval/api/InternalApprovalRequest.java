package com.example.copilot.approval.api;

import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import java.util.List;

public record InternalApprovalRequest(
        @NotEmpty @Size(max = 5) List<@Pattern(regexp = "[A-Z0-9_]{1,80}") String> reasonCodes,
        @Pattern(regexp = "sha256:[0-9a-f]{64}") String sqlFingerprint) {}
