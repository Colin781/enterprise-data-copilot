package com.example.copilot.analysis.service;

import com.example.copilot.analysis.api.AgentStepResource;
import com.example.copilot.analysis.api.RecordAgentStepRequest;
import com.example.copilot.analysis.domain.AgentStep;
import com.example.copilot.analysis.repository.AgentStepRepository;
import com.example.copilot.analysis.repository.AnalysisJobRepository;
import com.example.copilot.common.api.ResourceNotFoundException;
import com.example.copilot.events.JobProgressSignal;
import com.example.copilot.security.CallerIdentity.Caller;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.UUID;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.databind.ObjectMapper;

@Service
public class AgentStepService {

    private final AgentStepRepository stepRepository;
    private final AnalysisJobRepository jobRepository;
    private final ObjectMapper objectMapper;
    private final ApplicationEventPublisher eventPublisher;

    public AgentStepService(
            AgentStepRepository stepRepository,
            AnalysisJobRepository jobRepository,
            ObjectMapper objectMapper,
            ApplicationEventPublisher eventPublisher) {
        this.stepRepository = stepRepository;
        this.jobRepository = jobRepository;
        this.objectMapper = objectMapper;
        this.eventPublisher = eventPublisher;
    }

    @Transactional
    public AgentStepResource record(UUID jobId, RecordAgentStepRequest request) {
        var job = jobRepository
                .findById(jobId)
                .orElseThrow(() -> new ResourceNotFoundException("The analysis job was not found."));
        var existing = stepRepository.findByAnalysisJobIdAndStepNameAndAttemptAndStatus(
                jobId, request.stepName(), request.attempt(), request.status());
        if (existing.isPresent()) {
            return AgentStepResource.from(existing.get(), objectMapper);
        }
        var step = stepRepository.save(new AgentStep(
                UUID.randomUUID(),
                job.getTenantId(),
                jobId,
                request.stepName(),
                request.status(),
                request.attempt(),
                objectMapper.writeValueAsString(request.inputSummary()),
                objectMapper.writeValueAsString(request.outputSummary()),
                request.durationMs(),
                request.errorCode()));
        var payload = new LinkedHashMap<String, Object>();
        payload.put("step_name", request.stepName());
        payload.put("step_status", request.status());
        payload.put("attempt", request.attempt());
        if (request.errorCode() != null) {
            payload.put("error_code", request.errorCode());
        }
        eventPublisher.publishEvent(new JobProgressSignal(
                jobId, job.getTenantId(), job.getTraceId(), "AGENT_STEP", job.getStatus(), payload));
        return AgentStepResource.from(step, objectMapper);
    }

    @Transactional(readOnly = true)
    public List<AgentStepResource> list(UUID jobId, Caller caller) {
        var authorized = caller.roles().contains("ADMIN")
                ? jobRepository.findByIdAndTenantId(jobId, caller.tenantId())
                : jobRepository.findByIdAndTenantIdAndCreatedBy(jobId, caller.tenantId(), caller.userId());
        if (authorized.isEmpty()) {
            throw new ResourceNotFoundException("The analysis job was not found.");
        }
        return stepRepository.findAllByAnalysisJobIdOrderByCreatedAtAsc(jobId).stream()
                .map(step -> AgentStepResource.from(step, objectMapper))
                .toList();
    }
}
