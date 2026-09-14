package com.example.copilot.analysis.service;

import com.example.copilot.analysis.api.AnalysisJobResource;
import com.example.copilot.analysis.api.CreateAnalysisJobRequest;
import com.example.copilot.analysis.domain.AnalysisJob;
import com.example.copilot.analysis.repository.AnalysisJobRepository;
import com.example.copilot.audit.service.AuditService;
import com.example.copilot.common.api.IdempotencyConflictException;
import com.example.copilot.common.api.ResourceNotFoundException;
import com.example.copilot.datasource.repository.DataSourceRepository;
import com.example.copilot.identity.repository.AppUserRepository;
import com.example.copilot.security.CallerIdentity.Caller;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AnalysisJobService {

    private final AnalysisJobRepository jobRepository;
    private final DataSourceRepository dataSourceRepository;
    private final AppUserRepository userRepository;
    private final AuditService auditService;

    public AnalysisJobService(
            AnalysisJobRepository jobRepository,
            DataSourceRepository dataSourceRepository,
            AppUserRepository userRepository,
            AuditService auditService) {
        this.jobRepository = jobRepository;
        this.dataSourceRepository = dataSourceRepository;
        this.userRepository = userRepository;
        this.auditService = auditService;
    }

    @Transactional
    public AnalysisJobResource create(
            CreateAnalysisJobRequest request, String idempotencyKey, Caller caller, String traceId) {
        userRepository
                .findByIdAndTenantId(caller.userId(), caller.tenantId())
                .orElseThrow(() -> new ResourceNotFoundException("The authenticated user no longer exists."));

        var question = request.question().trim();
        var requestHash = requestHash(request.dataSourceId(), question);
        var existing = jobRepository.findByTenantIdAndCreatedByAndIdempotencyKey(
                caller.tenantId(), caller.userId(), idempotencyKey);
        if (existing.isPresent()) {
            if (!existing.get().getRequestHash().equals(requestHash)) {
                throw new IdempotencyConflictException();
            }
            return AnalysisJobResource.from(existing.get());
        }

        dataSourceRepository
                .findByIdAndTenantIdAndEnabledTrue(request.dataSourceId(), caller.tenantId())
                .orElseThrow(() -> new ResourceNotFoundException("The data source was not found."));

        var job = jobRepository.save(new AnalysisJob(
                UUID.randomUUID(),
                caller.tenantId(),
                request.dataSourceId(),
                caller.userId(),
                question,
                idempotencyKey,
                requestHash,
                traceId));
        auditService.recordSuccess(
                caller.tenantId(), caller.userId(), "ANALYSIS_JOB_CREATED", "ANALYSIS_JOB", job.getId(), traceId);
        return AnalysisJobResource.from(job);
    }

    @Transactional(readOnly = true)
    public AnalysisJobResource get(UUID jobId, Caller caller) {
        var job = caller.roles().contains("ADMIN")
                ? jobRepository.findByIdAndTenantId(jobId, caller.tenantId())
                : jobRepository.findByIdAndTenantIdAndCreatedBy(jobId, caller.tenantId(), caller.userId());
        return job.map(AnalysisJobResource::from)
                .orElseThrow(() -> new ResourceNotFoundException("The analysis job was not found."));
    }

    private static String requestHash(UUID dataSourceId, String question) {
        try {
            var digest = MessageDigest.getInstance("SHA-256");
            var bytes = digest.digest((dataSourceId + "\n" + question).getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(bytes);
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 is unavailable", exception);
        }
    }
}
