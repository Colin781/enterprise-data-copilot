package com.example.copilot.dto.response;

import java.util.UUID;

public class AnalysisJobQueryRow {

    private UUID id;
    private String question;
    private String status;

    public AnalysisJobQueryRow() {}

    public UUID getId() {
        return id;
    }

    public void setId(UUID id) {
        this.id = id;
    }

    public String getQuestion() {
        return question;
    }

    public void setQuestion(String question) {
        this.question = question;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }
}
