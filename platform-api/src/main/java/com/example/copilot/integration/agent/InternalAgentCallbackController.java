package com.example.copilot.integration.agent;

import com.example.copilot.analysis.api.AgentStepResource;
import com.example.copilot.analysis.api.RecordAgentStepRequest;
import com.example.copilot.analysis.service.AgentStepService;
import com.example.copilot.approval.api.ApprovalResource;
import com.example.copilot.approval.api.InternalApprovalRequest;
import com.example.copilot.approval.service.ApprovalService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import java.util.UUID;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/internal/v1/analysis/jobs/{jobId}")
public class InternalAgentCallbackController {

    private final InternalServiceAuthenticator authenticator;
    private final AgentStepService stepService;
    private final ApprovalService approvalService;

    public InternalAgentCallbackController(
            InternalServiceAuthenticator authenticator, AgentStepService stepService, ApprovalService approvalService) {
        this.authenticator = authenticator;
        this.stepService = stepService;
        this.approvalService = approvalService;
    }

    @PostMapping("/steps")
    public AgentStepResource recordStep(
            @PathVariable UUID jobId,
            @RequestHeader("Authorization") String authorization,
            @Valid @RequestBody RecordAgentStepRequest body) {
        authenticator.verify(authorization);
        return stepService.record(jobId, body);
    }

    @PostMapping("/approval-requests")
    public ApprovalResource requestApproval(
            @PathVariable UUID jobId,
            @RequestHeader("Authorization") String authorization,
            @Valid @RequestBody InternalApprovalRequest body,
            HttpServletRequest request) {
        authenticator.verify(authorization);
        var traceId = request.getHeader("X-Trace-Id");
        if (traceId == null || traceId.isBlank()) {
            traceId = UUID.randomUUID().toString().replace("-", "");
        }
        return approvalService.request(jobId, body, traceId);
    }
}
