package com.example.copilot.analysis.repository;

import com.example.copilot.analysis.domain.AgentStep;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface AgentStepRepository extends JpaRepository<AgentStep, UUID> {
    List<AgentStep> findAllByAnalysisJobIdOrderByCreatedAtAsc(UUID analysisJobId);

    Optional<AgentStep> findByAnalysisJobIdAndStepNameAndAttemptAndStatus(
            UUID analysisJobId, String stepName, int attempt, String status);
}
