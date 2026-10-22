package com.example.copilot.dto.response;

import java.util.List;

public record AnalysisJobSearchPage (
        List<AnalysisJobSearchItem> items,
        long total,
        int page,
        int size,
        long totalPages) {

    public AnalysisJobSearchPage{
        items = List.copyOf(items);
    }
}
