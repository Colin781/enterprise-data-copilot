package com.example.copilot.approval.service;

import com.example.copilot.analysis.domain.AnalysisJobStatus;
import com.example.copilot.analysis.repository.AnalysisJobRepository;
import com.example.copilot.approval.api.ApprovalResource;
import com.example.copilot.approval.api.InternalApprovalRequest;
import com.example.copilot.approval.domain.Approval;
import com.example.copilot.approval.domain.ApprovalStatus;
import com.example.copilot.approval.repository.ApprovalRepository;
import com.example.copilot.audit.service.AuditService;
import com.example.copilot.common.api.ApprovalAlreadyDecidedException;
import com.example.copilot.common.api.ResourceNotFoundException;
import com.example.copilot.events.JobProgressSignal;
import com.example.copilot.integration.agent.AgentRunClient;
import com.example.copilot.security.CallerIdentity.Caller;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ApprovalService {

    private final ApprovalRepository approvalRepository;
    private final AnalysisJobRepository jobRepository;
    private final AgentRunClient agentRunClient;
    private final AuditService auditService;
    private final ApplicationEventPublisher eventPublisher;

    public ApprovalService(
            ApprovalRepository approvalRepository,
            AnalysisJobRepository jobRepository,
            AgentRunClient agentRunClient,
            AuditService auditService,
            ApplicationEventPublisher eventPublisher) {
        this.approvalRepository = approvalRepository;
        this.jobRepository = jobRepository;
        this.agentRunClient = agentRunClient;
        this.auditService = auditService;
        this.eventPublisher = eventPublisher;
    }

    @Transactional
    public ApprovalResource request(UUID jobId, InternalApprovalRequest request, String traceId) {
        var job = jobRepository
                .findById(jobId)
                .orElseThrow(() -> new ResourceNotFoundException("The analysis job was not found."));
        var existing = approvalRepository.findByAnalysisJobIdAndTenantId(jobId, job.getTenantId());
        if (existing.isPresent()) {
            return ApprovalResource.from(existing.get());
        }
        advanceToWaiting(job);
        job.attachWorkflowThread(jobId.toString());
        var reason = String.join(",", request.reasonCodes());
        var approval = approvalRepository.save(
                new Approval(UUID.randomUUID(), job.getTenantId(), jobId, job.getCreatedBy(), reason));
        auditService.recordSuccess(
                job.getTenantId(), job.getCreatedBy(), "APPROVAL_REQUESTED", "APPROVAL", approval.getId(), traceId);
        eventPublisher.publishEvent(new JobProgressSignal(
                job.getId(),
                job.getTenantId(),
                job.getTraceId(),
                "APPROVAL_REQUIRED",
                AnalysisJobStatus.WAITING_APPROVAL,
                Map.of("approval_id", approval.getId().toString(), "reason_codes", request.reasonCodes())));
        return ApprovalResource.from(approval);
    }

    @Transactional
    public ApprovalResource decide(
            UUID approvalId, ApprovalStatus decision, String comment, Caller caller, String traceId) {
        var approval = approvalRepository
                .findForDecision(approvalId, caller.tenantId())
                .orElseThrow(() -> new ResourceNotFoundException("The approval was not found."));
        if (approval.getStatus() != ApprovalStatus.PENDING) {
            throw new ApprovalAlreadyDecidedException();
        }
        var job = jobRepository
                .findByIdAndTenantId(approval.getAnalysisJobId(), caller.tenantId())
                .orElseThrow(() -> new ResourceNotFoundException("The analysis job was not found."));
        var command = decision == ApprovalStatus.APPROVED ? "approved" : "rejected";
        var result =
                agentRunClient.resume(job.getId(), caller.tenantId(), approvalId, caller.userId(), command, comment);
        approval.decide(decision, caller.userId(), comment);
        if (decision == ApprovalStatus.REJECTED) {
            job.transitionTo(AnalysisJobStatus.REJECTED);
        } else {
            job.transitionTo(AnalysisJobStatus.RUNNING);
            if ("COMPLETED".equals(result.status())) {
                job.transitionTo(AnalysisJobStatus.COMPLETED);
            } else if ("FAILED".equals(result.status())) {
                job.transitionTo(AnalysisJobStatus.FAILED);
            }
        }
        if (result.state() != null) {
            job.storeAgentResult(
                    nodeText(result.state(), "sql"),
                    nodeText(result.state(), "answer"),
                    nodeText(result.state(), "error_code"),
                    nodeJson(result.state(), "columns"),
                    nodeJson(result.state(), "rows"),
                    nodeJson(result.state(), "chart_spec"),
                    nodeJson(result.state(), "citations"));
        }
        auditService.recordSuccess(
                caller.tenantId(),
                caller.userId(),
                decision == ApprovalStatus.APPROVED ? "APPROVAL_APPROVED" : "APPROVAL_REJECTED",
                "APPROVAL",
                approvalId,
                traceId);
        eventPublisher.publishEvent(new JobProgressSignal(
                job.getId(),
                job.getTenantId(),
                job.getTraceId(),
                "APPROVAL_DECIDED",
                job.getStatus(),
                Map.of("approval_id", approvalId.toString(), "decision", command)));
        return ApprovalResource.from(approval);
    }

    @Transactional(readOnly = true)
    public List<ApprovalResource> list(Caller caller) {
        return approvalRepository.findTop50ByTenantIdOrderByCreatedAtDesc(caller.tenantId()).stream()
                .map(ApprovalResource::from)
                .toList();
    }

    private static void advanceToWaiting(com.example.copilot.analysis.domain.AnalysisJob job) {
        if (job.getStatus() == AnalysisJobStatus.CREATED) {
            job.transitionTo(AnalysisJobStatus.PLANNING);
        }
        if (job.getStatus() == AnalysisJobStatus.PLANNING) {
            job.transitionTo(AnalysisJobStatus.VALIDATING);
        }
        job.transitionTo(AnalysisJobStatus.WAITING_APPROVAL);
    }

    private static String nodeText(tools.jackson.databind.JsonNode state, String field) {
        var value = state.get(field);
        return value == null || value.isNull() ? null : value.asText();
    }

    private static String nodeJson(tools.jackson.databind.JsonNode state, String field) {
        var value = state.get(field);
        return value == null || value.isNull() ? null : value.toString();
    }
}
