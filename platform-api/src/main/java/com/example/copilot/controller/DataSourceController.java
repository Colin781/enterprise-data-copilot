package com.example.copilot.controller;

import com.example.copilot.common.TraceContext;
import com.example.copilot.dto.request.CreateDataSourceRequest;
import com.example.copilot.dto.response.DataSourceResource;
import com.example.copilot.security.CallerIdentity;
import com.example.copilot.service.DataSourceManagementService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import java.net.URI;
import java.util.List;
import java.util.UUID;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/data-sources")
public class DataSourceController {

    private final DataSourceManagementService dataSourceService;
    private final CallerIdentity callerIdentity;

    public DataSourceController(DataSourceManagementService dataSourceService, CallerIdentity callerIdentity) {
        this.dataSourceService = dataSourceService;
        this.callerIdentity = callerIdentity;
    }

    @GetMapping("/{id}")
    @PreAuthorize("hasAnyRole('ADMIN', 'ANALYST', 'VIEWER')")
    public DataSourceResource get(@PathVariable("id") UUID id, JwtAuthenticationToken authentication) {
        return dataSourceService.get(id, callerIdentity.current(authentication));
    }

    @PostMapping
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<DataSourceResource> create(
            @Valid @RequestBody CreateDataSourceRequest body,
            JwtAuthenticationToken authentication,
            HttpServletRequest request) {
        var resource =
                dataSourceService.create(body, callerIdentity.current(authentication), TraceContext.current(request));
        return ResponseEntity.created(URI.create("/api/data-sources/" + resource.id()))
                .body(resource);
    }

    @GetMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'ANALYST', 'VIEWER')")
    public List<DataSourceResource> list(JwtAuthenticationToken authentication) {
        return dataSourceService.list(callerIdentity.current(authentication));
    }
}
