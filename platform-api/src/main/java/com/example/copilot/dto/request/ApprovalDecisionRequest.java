package com.example.copilot.dto.request;

import jakarta.validation.constraints.Size;

public record ApprovalDecisionRequest(@Size(max = 500) String comment) {}
