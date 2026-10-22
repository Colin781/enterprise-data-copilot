package com.example.copilot.dto.request;

import com.example.copilot.enums.AnalysisJobStatus;

import java.time.Instant;
import java.util.List;
import java.util.Objects;

public record AnalysisJobSearchCriteria(
        List<AnalysisJobStatus> statuses,
        String keyword,
        Instant createdFrom,
        Instant createdTo) {

    public AnalysisJobSearchCriteria {
        if (statuses != null){
            if (statuses.isEmpty()) {
                throw new IllegalArgumentException(
                        "statuses must be null or contain at least one status");
            }

            if(statuses.stream().anyMatch(Objects::isNull)) {
                throw new IllegalArgumentException(
                        "statuses must not contain null");
            }

            statuses = List.copyOf(statuses);
        }

        if (keyword != null){
            keyword = keyword.strip();

            if (keyword.isEmpty()) {
                keyword = null;
            }
        }

        if (createdFrom != null
                && createdTo != null
                && createdFrom.isAfter(createdTo)) {
            throw new IllegalArgumentException(
                    "createdFrom must not be after createdTo");
        }
    }

    public String keywordPattern() {
        if (keyword == null) {
            return null;
        }

        String escaped = keyword
                .replace("!", "!!")
                .replace("%", "!%")
                .replace("_", "!_");

        return "%" + escaped + "%";
    }

}
