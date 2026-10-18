package com.example.copilot.exception;

import com.example.copilot.enums.AnalysisJobStatus;

public final class InvalidJobTransitionException extends IllegalStateException {

    public InvalidJobTransitionException(AnalysisJobStatus current, AnalysisJobStatus target) {
        super("Analysis job cannot transition from " + current + " to " + target);
    }
}
