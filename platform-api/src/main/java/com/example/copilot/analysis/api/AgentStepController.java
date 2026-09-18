package com.example.copilot.analysis.api;

import com.example.copilot.analysis.service.AgentStepService;
import com.example.copilot.security.CallerIdentity;
import java.util.List;
import java.util.UUID;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/analysis/jobs/{jobId}/steps")
public class AgentStepController {

    private final AgentStepService stepService;
    private final CallerIdentity callerIdentity;

    public AgentStepController(AgentStepService stepService, CallerIdentity callerIdentity) {
        this.stepService = stepService;
        this.callerIdentity = callerIdentity;
    }

    @GetMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'ANALYST', 'VIEWER')")
    public List<AgentStepResource> list(@PathVariable UUID jobId, JwtAuthenticationToken authentication) {
        return stepService.list(jobId, callerIdentity.current(authentication));
    }
}
