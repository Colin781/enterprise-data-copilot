package com.example.copilot.dto.request;

import com.example.copilot.enums.AnalysisJobStatus;
import com.example.copilot.exception.InvalidAnalysisJobSearchException;
import org.springframework.util.MultiValueMap;

import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.UUID;



public record AnalysisJobSearchRequest (
        AnalysisJobSearchCriteria criteria,
        UUID dataSourceId,
        int page,
        int size) {

    private static final Set<String> ALLOWED_PARAMETERS = Set.of(
            "statuses",
            "keyword",
            "data_source_id",
            "created_from",
            "created_to",
            "page",
            "size");

    public AnalysisJobSearchRequest{
        if (criteria == null){
            throw invalid("criteria is required");
        }

        if (page < 1 || page > 10_000) {
            throw invalid("page must be between 1 and 10000");
        }

        if (size < 1 || size > 100) {
            throw invalid("size must be between 1 and 100");
        }

        if (criteria.keyword() != null
                && criteria.keyword().length() > 200) {
            throw invalid("keyword must contain at most 200 characters");
        }
    }

    public static AnalysisJobSearchRequest from(
            MultiValueMap<String, String> parameters) {

        if(!ALLOWED_PARAMETERS.containsAll(parameters.keySet())) {
            throw invalid("The query contains an unsupported parameter");
        }

        try {
            var criteria = new AnalysisJobSearchCriteria(
                    parseStatuses(parameters.get("statuses")),
                    single(parameters, "keyword"),
                    parseTime(
                            single(parameters, "created_from"),
                            "created_from"),
                    parseTime(
                            single(parameters, "created_to"),
                            "created_to"));


            return new AnalysisJobSearchRequest(
                    criteria,
                    parseUuid(single(parameters, "data_source_id")),
                    parseInteger(single(parameters, "page"), 1, "page"),
                    parseInteger(single(parameters, "size"), 20, "size"));
        } catch (IllegalArgumentException exception) {
            throw invalid("The status list or time range is invalid");
        }
    }

    public long offset(){
        return ((long) page - 1) * size;
    }

    private static String single(
            MultiValueMap<String, String> parameters,
            String name) {

        var values = parameters.get(name);

        if (values == null) {
            return null;
        }

        if (values.size() != 1 || values.getFirst() == null) {
            throw invalid(name + " must be supplied exactly once");
        }

        return values.getFirst();
    }

    private static List<AnalysisJobStatus> parseStatuses(
            List<String> values) {
        if (values == null) {
            return null;
        }

        if (values.isEmpty()
                || values.size() > AnalysisJobStatus.values().length) {
            throw invalid("statuses must contain between 1 and 9 values");
        }

        var result = new ArrayList<AnalysisJobStatus>();

        for (var value : values) {
            if (value == null || value.isBlank()) {
                throw invalid("statuses must not contain an empty value");
            }

            try {
                result.add(AnalysisJobStatus.valueOf(value.strip()));
            } catch (IllegalArgumentException exception) {
                throw invalid("statuses contains an unknown status");
            }
        }

        return result.stream().distinct().toList();
    }

    private static UUID parseUuid(String value) {
        if(value == null) {
            return null;
        }

        try {
            var id = UUID.fromString(value);

            if(!id.toString().equalsIgnoreCase(value)) {
                throw invalid("data_source_id must be a canonical UUID");
            }

            return id;
        } catch (IllegalArgumentException exception) {
            throw invalid("data_source_id must be a UUID");
        }
    }

    private static Instant parseTime(String value, String name){
        if (value == null) {
            return null;
        }

        try {
            return OffsetDateTime.parse(value).toInstant();
        } catch (DateTimeParseException exception) {
            throw invalid(
                    name + " must be an ISO-8601 timestamp with a timezone");
        }
    }

    private static int parseInteger(
            String value,
            int defaultValue,
            String name) {

        if (value == null) {
            return defaultValue;
        }

        try {
            return Integer.parseInt(value);
        } catch (NumberFormatException exception){
            throw invalid(name + " must be an integer");
        }
    }

    private static InvalidAnalysisJobSearchException invalid(
            String message) {
        return new InvalidAnalysisJobSearchException(message);
    }

}



