package com.example.copilot.datasource.api;

import com.example.copilot.common.TraceContext;
import com.example.copilot.datasource.service.DataSourceManagementService;
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
@RequestMapping("/api/data-sources")
public class DataSourceController {

    private final DataSourceManagementService dataSourceService;
    private final CallerIdentity callerIdentity;

    public DataSourceController(DataSourceManagementService dataSourceService, CallerIdentity callerIdentity) {
        this.dataSourceService = dataSourceService;
        this.callerIdentity = callerIdentity;
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
