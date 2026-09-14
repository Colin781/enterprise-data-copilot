package com.example.copilot.analysis.domain;

public enum AnalysisJobStatus {
    CREATED,
    PLANNING,
    VALIDATING,
    WAITING_APPROVAL,
    RUNNING,
    COMPLETED,
    REJECTED,
    FAILED,
    CANCELLED
}
