package com.example.copilot.analysis.api;

import com.example.copilot.analysis.service.AnalysisJobService;
import com.example.copilot.common.TraceContext;
import com.example.copilot.events.AnalysisEventStreamService;
import com.example.copilot.security.CallerIdentity;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Size;
import java.net.URI;
import java.util.List;
import java.util.UUID;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

@Validated
@RestController
@RequestMapping("/api/analysis/jobs")
public class AnalysisJobController {

    private final AnalysisJobService jobService;
    private final CallerIdentity callerIdentity;
    private final AnalysisEventStreamService eventStream;

    public AnalysisJobController(
            AnalysisJobService jobService, CallerIdentity callerIdentity, AnalysisEventStreamService eventStream) {
        this.jobService = jobService;
        this.callerIdentity = callerIdentity;
        this.eventStream = eventStream;
    }

    @PostMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'ANALYST')")
    public ResponseEntity<AnalysisJobResource> create(
            @Valid @RequestBody CreateAnalysisJobRequest body,
            @RequestHeader("Idempotency-Key") @Size(min = 16, max = 128) String idempotencyKey,
            JwtAuthenticationToken authentication,
            HttpServletRequest request) {
        var resource = jobService.create(
                body, idempotencyKey, callerIdentity.current(authentication), TraceContext.current(request));
        return ResponseEntity.accepted()
                .location(URI.create("/api/analysis/jobs/" + resource.id()))
                .body(resource);
    }

    @GetMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'ANALYST', 'VIEWER')")
    public List<AnalysisJobResource> list(JwtAuthenticationToken authentication) {
        return jobService.list(callerIdentity.current(authentication));
    }

    @GetMapping("/{jobId}")
    @PreAuthorize("hasAnyRole('ADMIN', 'ANALYST', 'VIEWER')")
    public AnalysisJobResource get(@PathVariable UUID jobId, JwtAuthenticationToken authentication) {
        return jobService.get(jobId, callerIdentity.current(authentication));
    }

    @GetMapping(value = "/{jobId}/events", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    @PreAuthorize("hasAnyRole('ADMIN', 'ANALYST', 'VIEWER')")
    public SseEmitter events(
            @PathVariable UUID jobId,
            @RequestHeader(value = "Last-Event-ID", required = false) String lastEventId,
            JwtAuthenticationToken authentication) {
        var caller = callerIdentity.current(authentication);
        var snapshot = jobService.get(jobId, caller);
        return eventStream.subscribe(snapshot, caller.tenantId(), lastEventId);
    }
}
