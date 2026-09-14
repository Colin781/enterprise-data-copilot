package com.example.copilot.analysis.domain;

public final class InvalidJobTransitionException extends IllegalStateException {

    public InvalidJobTransitionException(AnalysisJobStatus current, AnalysisJobStatus target) {
        super("Analysis job cannot transition from " + current + " to " + target);
    }
}
