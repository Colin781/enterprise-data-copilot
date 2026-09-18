package com.example.copilot.approval.api;

import com.example.copilot.approval.domain.ApprovalStatus;
import com.example.copilot.approval.service.ApprovalService;
import com.example.copilot.common.TraceContext;
import com.example.copilot.security.CallerIdentity;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import java.util.List;
import java.util.UUID;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/approvals")
public class ApprovalController {

    private final ApprovalService approvalService;
    private final CallerIdentity callerIdentity;

    public ApprovalController(ApprovalService approvalService, CallerIdentity callerIdentity) {
        this.approvalService = approvalService;
        this.callerIdentity = callerIdentity;
    }

    @GetMapping
    @PreAuthorize("hasRole('ADMIN')")
    public List<ApprovalResource> list(JwtAuthenticationToken authentication) {
        return approvalService.list(callerIdentity.current(authentication));
    }

    @PostMapping("/{approvalId}/approve")
    @PreAuthorize("hasRole('ADMIN')")
    public ApprovalResource approve(
            @PathVariable UUID approvalId,
            @Valid @RequestBody ApprovalDecisionRequest body,
            JwtAuthenticationToken authentication,
            HttpServletRequest request) {
        return approvalService.decide(
                approvalId,
                ApprovalStatus.APPROVED,
                body.comment(),
                callerIdentity.current(authentication),
                TraceContext.current(request));
    }

    @PostMapping("/{approvalId}/reject")
    @PreAuthorize("hasRole('ADMIN')")
    public ApprovalResource reject(
            @PathVariable UUID approvalId,
            @Valid @RequestBody ApprovalDecisionRequest body,
            JwtAuthenticationToken authentication,
            HttpServletRequest request) {
        return approvalService.decide(
                approvalId,
                ApprovalStatus.REJECTED,
                body.comment(),
                callerIdentity.current(authentication),
                TraceContext.current(request));
    }
}
