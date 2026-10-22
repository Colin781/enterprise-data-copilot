package com.example.copilot.controller;

import com.example.copilot.common.TraceContext;
import com.example.copilot.dto.request.AnalysisJobSearchRequest;
import com.example.copilot.dto.response.AnalysisJobSearchPage;
import com.example.copilot.dto.response.ApiError;
import com.example.copilot.exception.InvalidAnalysisJobSearchException;
import com.example.copilot.security.CallerIdentity;
import com.example.copilot.service.AnalysisJobQueryService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.util.MultiValueMap;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/analysis/jobs/search")
public class AnalysisJobSearchController {

    private final AnalysisJobQueryService service;
    private final CallerIdentity callerIdentity;

    public AnalysisJobSearchController(
            AnalysisJobQueryService service,
            CallerIdentity callerIdentity) {
        this.service = service;
        this.callerIdentity = callerIdentity;
    }

    @GetMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'ANALYST', 'VIEWER')")
    public AnalysisJobSearchPage search(
            @RequestParam MultiValueMap<String, String> parameters,
            JwtAuthenticationToken authentication) {

        var request = AnalysisJobSearchRequest.from(parameters);
        var caller = callerIdentity.current(authentication);

        return service.search(request, caller);
    }

    @ExceptionHandler(InvalidAnalysisJobSearchException.class)
    public ResponseEntity<ApiError> invaludSearch(
            InvalidAnalysisJobSearchException exception,
            HttpServletRequest request) {

        return ResponseEntity.badRequest().body(
                ApiError.of(
                        "INVALID_ANALYSIS_JOB_SEARCH",
                        exception.getMessage(),
                        TraceContext.current(request)));
    }
}
