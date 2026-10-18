package com.example.copilot.dto.response;

import com.example.copilot.entity.DataSource;
import java.util.UUID;

public record DataSourceResource(
        UUID id, String name, String sourceType, String allowedSchema, boolean enabled, long version) {

    public static DataSourceResource from(DataSource dataSource) {
        return new DataSourceResource(
                dataSource.getId(),
                dataSource.getName(),
                dataSource.getSourceType(),
                dataSource.getAllowedSchema(),
                dataSource.isEnabled(),
                dataSource.getVersion());
    }
}
