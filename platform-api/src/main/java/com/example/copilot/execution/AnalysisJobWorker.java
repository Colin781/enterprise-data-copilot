package com.example.copilot.execution;

import com.example.copilot.analysis.domain.AnalysisJob;
import com.example.copilot.analysis.domain.AnalysisJobStatus;
import com.example.copilot.analysis.repository.AnalysisJobRepository;
import com.example.copilot.events.AnalysisEventStreamService;
import com.example.copilot.events.JobProgressSignal;
import com.example.copilot.identity.domain.UserRole;
import com.example.copilot.identity.repository.AppUserRepository;
import com.example.copilot.integration.agent.AgentRunClient;
import com.example.copilot.integration.agent.AgentRunResult;
import java.time.Duration;
import java.util.Map;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionTemplate;
import tools.jackson.databind.JsonNode;

@Component
public class AnalysisJobWorker {

    private static final Logger LOGGER = LoggerFactory.getLogger(AnalysisJobWorker.class);

    private final AnalysisJobRepository jobRepository;
    private final AppUserRepository userRepository;
    private final AgentRunClient agentRunClient;
    private final AnalysisEventStreamService eventStream;
    private final JobDispatchLease lease;
    private final AnalysisExecutionProperties properties;
    private final TransactionTemplate transactions;

    public AnalysisJobWorker(
            AnalysisJobRepository jobRepository,
            AppUserRepository userRepository,
            AgentRunClient agentRunClient,
            AnalysisEventStreamService eventStream,
            JobDispatchLease lease,
            AnalysisExecutionProperties properties,
            TransactionTemplate transactions) {
        this.jobRepository = jobRepository;
        this.userRepository = userRepository;
        this.agentRunClient = agentRunClient;
        this.eventStream = eventStream;
        this.lease = lease;
        this.properties = properties;
        this.transactions = transactions;
    }

    public void execute(UUID jobId) {
        var owner = UUID.randomUUID().toString();
        if (!lease.acquire(jobId, owner)) {
            return;
        }
        try {
            var dispatch = transactions.execute(status -> prepare(jobId));
            if (dispatch == null) {
                return;
            }
            publish(dispatch, "JOB_STATUS_CHANGED", AnalysisJobStatus.PLANNING, Map.of("attempt", 0));
            var result = callAgent(dispatch);
            var completed = transactions.execute(status -> persistResult(jobId, result));
            if (completed != null) {
                publish(
                        completed,
                        "JOB_STATUS_CHANGED",
                        completed.status(),
                        Map.of("terminal", isTerminal(completed.status())));
            }
        } catch (RuntimeException exception) {
            LOGGER.error("Background agent execution failed for job {}", jobId, exception);
            fail(jobId, "AGENT_DISPATCH_FAILED");
        } finally {
            lease.release(jobId, owner);
        }
    }

    public void reject(UUID jobId) {
        fail(jobId, "ASYNC_QUEUE_FULL");
    }

    private DispatchData prepare(UUID jobId) {
        var job = jobRepository.findById(jobId).orElse(null);
        if (job == null || isTerminal(job.getStatus()) || job.getStatus() == AnalysisJobStatus.WAITING_APPROVAL) {
            return null;
        }
        if (job.getStatus() == AnalysisJobStatus.CREATED) {
            job.transitionTo(AnalysisJobStatus.PLANNING);
        }
        var user = userRepository.findById(job.getCreatedBy()).orElseThrow();
        var role = user.getRoles().contains(UserRole.ADMIN) ? "ADMIN" : "ANALYST";
        return data(job, role);
    }

    private AgentRunResult callAgent(DispatchData job) {
        RuntimeException lastFailure = null;
        for (var attempt = 1; attempt <= properties.maxAttempts(); attempt++) {
            try {
                return agentRunClient.start(
                        job.jobId(),
                        job.tenantId(),
                        job.userId(),
                        job.role(),
                        job.dataSourceId(),
                        job.question(),
                        job.traceId(),
                        job.idempotencyKey());
            } catch (RuntimeException exception) {
                lastFailure = exception;
                if (attempt < properties.maxAttempts()) {
                    pause(properties.retryBackoff().multipliedBy(attempt));
                }
            }
        }
        throw lastFailure == null ? new IllegalStateException("Agent execution failed") : lastFailure;
    }

    private DispatchData persistResult(UUID jobId, AgentRunResult result) {
        if (result == null) {
            throw new IllegalStateException("Agent returned an empty response");
        }
        var job = jobRepository.findById(jobId).orElseThrow();
        if (isTerminal(job.getStatus())) {
            return null;
        }
        var target = AnalysisJobStatus.valueOf(result.status());
        advance(job, target);
        job.attachWorkflowThread(result.runId());
        job.storeAgentResult(
                stateText(result.state(), "sql"),
                stateText(result.state(), "answer"),
                stateText(result.state(), "error_code"),
                stateJson(result.state(), "columns"),
                stateJson(result.state(), "rows"),
                stateJson(result.state(), "chart_spec"),
                stateJson(result.state(), "citations"));
        return data(job, null);
    }

    private void fail(UUID jobId, String errorCode) {
        var failed = transactions.execute(status -> {
            var job = jobRepository.findById(jobId).orElse(null);
            if (job == null || isTerminal(job.getStatus())) {
                return null;
            }
            job.transitionTo(AnalysisJobStatus.FAILED);
            job.storeAgentResult(null, null, errorCode);
            return data(job, null);
        });
        if (failed != null) {
            publish(failed, "JOB_STATUS_CHANGED", AnalysisJobStatus.FAILED, Map.of("error_code", errorCode));
        }
    }

    private void publish(DispatchData job, String type, AnalysisJobStatus status, Map<String, Object> payload) {
        eventStream.publish(new JobProgressSignal(job.jobId(), job.tenantId(), job.traceId(), type, status, payload));
    }

    private static void advance(AnalysisJob job, AnalysisJobStatus target) {
        if (target == AnalysisJobStatus.PLANNING) {
            if (job.getStatus() == AnalysisJobStatus.CREATED) {
                job.transitionTo(target);
            }
            return;
        }
        if (job.getStatus() == AnalysisJobStatus.CREATED) {
            job.transitionTo(AnalysisJobStatus.PLANNING);
        }
        if (target != AnalysisJobStatus.FAILED && job.getStatus() == AnalysisJobStatus.PLANNING) {
            job.transitionTo(AnalysisJobStatus.VALIDATING);
        }
        if (target == AnalysisJobStatus.COMPLETED && job.getStatus() != AnalysisJobStatus.RUNNING) {
            job.transitionTo(AnalysisJobStatus.RUNNING);
        }
        if (job.getStatus() != target) {
            job.transitionTo(target);
        }
    }

    private static String stateText(JsonNode state, String field) {
        if (state == null) {
            return null;
        }
        var value = state.get(field);
        return value == null || value.isNull() ? null : value.asText();
    }

    private static String stateJson(JsonNode state, String field) {
        if (state == null) {
            return null;
        }
        var value = state.get(field);
        return value == null || value.isNull() ? null : value.toString();
    }

    private static boolean isTerminal(AnalysisJobStatus status) {
        return status == AnalysisJobStatus.COMPLETED
                || status == AnalysisJobStatus.REJECTED
                || status == AnalysisJobStatus.FAILED
                || status == AnalysisJobStatus.CANCELLED;
    }

    private static DispatchData data(AnalysisJob job, String role) {
        return new DispatchData(
                job.getId(),
                job.getTenantId(),
                job.getCreatedBy(),
                role,
                job.getDataSourceId(),
                job.getQuestion(),
                job.getTraceId(),
                job.getIdempotencyKey(),
                job.getStatus());
    }

    private static void pause(Duration duration) {
        try {
            Thread.sleep(duration);
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("Agent retry interrupted", exception);
        }
    }

    private record DispatchData(
            UUID jobId,
            UUID tenantId,
            UUID userId,
            String role,
            UUID dataSourceId,
            String question,
            String traceId,
            String idempotencyKey,
            AnalysisJobStatus status) {}
}
