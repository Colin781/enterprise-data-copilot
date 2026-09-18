package com.example.copilot.execution;

import com.example.copilot.analysis.domain.AnalysisJobStatus;
import com.example.copilot.analysis.repository.AnalysisJobRepository;
import com.example.copilot.events.AnalysisEventStreamService;
import com.example.copilot.events.JobProgressSignal;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.RejectedExecutionException;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

@Component
public class AnalysisJobDispatcher {

    private final AnalysisExecutionProperties properties;
    private final ThreadPoolTaskExecutor executor;
    private final AnalysisJobWorker worker;
    private final AnalysisJobRepository jobRepository;
    private final AnalysisEventStreamService eventStream;

    public AnalysisJobDispatcher(
            AnalysisExecutionProperties properties,
            @Qualifier("analysisJobExecutor") ThreadPoolTaskExecutor executor,
            AnalysisJobWorker worker,
            AnalysisJobRepository jobRepository,
            AnalysisEventStreamService eventStream) {
        this.properties = properties;
        this.executor = executor;
        this.worker = worker;
        this.jobRepository = jobRepository;
        this.eventStream = eventStream;
    }

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void onAccepted(AnalysisJobAccepted accepted) {
        if (properties.enabled()) {
            enqueue(accepted.jobId(), false);
        }
    }

    @EventListener(ApplicationReadyEvent.class)
    public void recoverUnfinishedJobs() {
        if (!properties.enabled()) {
            return;
        }
        jobRepository
                .findAllByStatusIn(Set.of(AnalysisJobStatus.CREATED, AnalysisJobStatus.PLANNING))
                .forEach(job -> enqueue(job.getId(), true));
    }

    private void enqueue(UUID jobId, boolean recovered) {
        try {
            executor.execute(() -> {
                jobRepository
                        .findById(jobId)
                        .ifPresent(job -> eventStream.publish(new JobProgressSignal(
                                job.getId(),
                                job.getTenantId(),
                                job.getTraceId(),
                                recovered ? "JOB_RECOVERED" : "JOB_ACCEPTED",
                                job.getStatus(),
                                Map.of("recovered", recovered))));
                worker.execute(jobId);
            });
        } catch (RejectedExecutionException exception) {
            worker.reject(jobId);
        }
    }
}
