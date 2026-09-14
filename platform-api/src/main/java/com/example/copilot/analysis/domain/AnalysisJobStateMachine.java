package com.example.copilot.analysis.domain;

import java.util.Map;
import java.util.Objects;
import java.util.Set;

public final class AnalysisJobStateMachine {

    private static final Set<AnalysisJobStatus> TERMINAL_STATES = Set.of(
            AnalysisJobStatus.COMPLETED,
            AnalysisJobStatus.REJECTED,
            AnalysisJobStatus.FAILED,
            AnalysisJobStatus.CANCELLED);

    private static final Map<AnalysisJobStatus, Set<AnalysisJobStatus>> ALLOWED_TRANSITIONS = Map.of(
            AnalysisJobStatus.CREATED,
            Set.of(AnalysisJobStatus.PLANNING, AnalysisJobStatus.FAILED, AnalysisJobStatus.CANCELLED),
            AnalysisJobStatus.PLANNING,
            Set.of(AnalysisJobStatus.VALIDATING, AnalysisJobStatus.FAILED, AnalysisJobStatus.CANCELLED),
            AnalysisJobStatus.VALIDATING,
            Set.of(
                    AnalysisJobStatus.RUNNING,
                    AnalysisJobStatus.WAITING_APPROVAL,
                    AnalysisJobStatus.REJECTED,
                    AnalysisJobStatus.FAILED,
                    AnalysisJobStatus.CANCELLED),
            AnalysisJobStatus.WAITING_APPROVAL,
            Set.of(
                    AnalysisJobStatus.RUNNING,
                    AnalysisJobStatus.REJECTED,
                    AnalysisJobStatus.FAILED,
                    AnalysisJobStatus.CANCELLED),
            AnalysisJobStatus.RUNNING,
            Set.of(AnalysisJobStatus.COMPLETED, AnalysisJobStatus.FAILED, AnalysisJobStatus.CANCELLED));

    public boolean canTransition(AnalysisJobStatus current, AnalysisJobStatus target) {
        Objects.requireNonNull(current, "current status must not be null");
        Objects.requireNonNull(target, "target status must not be null");

        // Replayed status updates are treated as idempotent no-ops.
        return current == target
                || ALLOWED_TRANSITIONS.getOrDefault(current, Set.of()).contains(target);
    }

    public AnalysisJobStatus transition(AnalysisJobStatus current, AnalysisJobStatus target) {
        if (!canTransition(current, target)) {
            throw new InvalidJobTransitionException(current, target);
        }
        return target;
    }

    public boolean isTerminal(AnalysisJobStatus status) {
        Objects.requireNonNull(status, "status must not be null");
        return TERMINAL_STATES.contains(status);
    }
}
