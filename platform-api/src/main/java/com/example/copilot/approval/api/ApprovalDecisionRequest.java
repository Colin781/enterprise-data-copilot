package com.example.copilot.approval.api;

import jakarta.validation.constraints.Size;

public record ApprovalDecisionRequest(@Size(max = 500) String comment) {}
