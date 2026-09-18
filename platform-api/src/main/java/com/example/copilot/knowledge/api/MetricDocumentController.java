package com.example.copilot.knowledge.api;

import com.example.copilot.common.TraceContext;
import com.example.copilot.knowledge.service.MetricDocumentService;
import com.example.copilot.security.CallerIdentity;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import java.net.URI;
import java.util.List;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/metric-documents")
public class MetricDocumentController {

    private final MetricDocumentService service;
    private final CallerIdentity callerIdentity;

    public MetricDocumentController(MetricDocumentService service, CallerIdentity callerIdentity) {
        this.service = service;
        this.callerIdentity = callerIdentity;
    }

    @GetMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'ANALYST', 'VIEWER')")
    public List<MetricDocumentResource> list(JwtAuthenticationToken authentication) {
        return service.list(callerIdentity.current(authentication));
    }

    @PostMapping
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<MetricDocumentResource> upload(
            @Valid @RequestBody MetricDocumentUploadRequest request,
            JwtAuthenticationToken authentication,
            HttpServletRequest servletRequest) {
        var resource =
                service.upload(request, callerIdentity.current(authentication), TraceContext.current(servletRequest));
        return ResponseEntity.created(URI.create("/api/metric-documents/" + resource.id()))
                .body(resource);
    }
}
