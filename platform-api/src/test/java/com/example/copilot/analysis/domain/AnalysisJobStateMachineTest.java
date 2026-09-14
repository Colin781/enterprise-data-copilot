package com.example.copilot.analysis.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;

class AnalysisJobStateMachineTest {

    private final AnalysisJobStateMachine stateMachine = new AnalysisJobStateMachine();

    @Test
    void supportsSuccessfulAnalysisPath() {
        assertTransition(AnalysisJobStatus.CREATED, AnalysisJobStatus.PLANNING);
        assertTransition(AnalysisJobStatus.PLANNING, AnalysisJobStatus.VALIDATING);
        assertTransition(AnalysisJobStatus.VALIDATING, AnalysisJobStatus.RUNNING);
        assertTransition(AnalysisJobStatus.RUNNING, AnalysisJobStatus.COMPLETED);
    }

    @Test
    void supportsApprovalAndRejectionBranches() {
        assertTransition(AnalysisJobStatus.VALIDATING, AnalysisJobStatus.WAITING_APPROVAL);
        assertTransition(AnalysisJobStatus.WAITING_APPROVAL, AnalysisJobStatus.RUNNING);
        assertTransition(AnalysisJobStatus.WAITING_APPROVAL, AnalysisJobStatus.REJECTED);
        assertTransition(AnalysisJobStatus.VALIDATING, AnalysisJobStatus.REJECTED);
    }

    @Test
    void allowsFailureAndCancellationFromEveryNonTerminalState() {
        for (var status : new AnalysisJobStatus[] {
            AnalysisJobStatus.CREATED,
            AnalysisJobStatus.PLANNING,
            AnalysisJobStatus.VALIDATING,
            AnalysisJobStatus.WAITING_APPROVAL,
            AnalysisJobStatus.RUNNING
        }) {
            assertTransition(status, AnalysisJobStatus.FAILED);
            assertTransition(status, AnalysisJobStatus.CANCELLED);
        }
    }

    @Test
    void treatsRepeatedUpdatesAsIdempotent() {
        for (var status : AnalysisJobStatus.values()) {
            assertTransition(status, status);
        }
    }

    @Test
    void identifiesTerminalStates() {
        assertThat(stateMachine.isTerminal(AnalysisJobStatus.COMPLETED)).isTrue();
        assertThat(stateMachine.isTerminal(AnalysisJobStatus.REJECTED)).isTrue();
        assertThat(stateMachine.isTerminal(AnalysisJobStatus.FAILED)).isTrue();
        assertThat(stateMachine.isTerminal(AnalysisJobStatus.CANCELLED)).isTrue();
        assertThat(stateMachine.isTerminal(AnalysisJobStatus.RUNNING)).isFalse();
    }

    @Test
    void rejectsSkippedAndTerminalTransitions() {
        assertThatThrownBy(() -> stateMachine.transition(AnalysisJobStatus.CREATED, AnalysisJobStatus.COMPLETED))
                .isInstanceOf(InvalidJobTransitionException.class)
                .hasMessageContaining("CREATED")
                .hasMessageContaining("COMPLETED");

        assertThatThrownBy(() -> stateMachine.transition(AnalysisJobStatus.COMPLETED, AnalysisJobStatus.RUNNING))
                .isInstanceOf(InvalidJobTransitionException.class);
    }

    private void assertTransition(AnalysisJobStatus current, AnalysisJobStatus target) {
        assertThat(stateMachine.canTransition(current, target)).isTrue();
        assertThat(stateMachine.transition(current, target)).isEqualTo(target);
    }
}
