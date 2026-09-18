package com.example.copilot.events;

import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

@Component
public class JobProgressSignalListener {

    private final AnalysisEventStreamService eventStream;

    public JobProgressSignalListener(AnalysisEventStreamService eventStream) {
        this.eventStream = eventStream;
    }

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void publish(JobProgressSignal signal) {
        eventStream.publish(signal);
    }
}
