package com.example.copilot.datasource.repository;

import com.example.copilot.datasource.domain.DataSource;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface DataSourceRepository extends JpaRepository<DataSource, UUID> {
    Optional<DataSource> findByIdAndTenantIdAndEnabledTrue(UUID id, UUID tenantId);

    List<DataSource> findAllByTenantIdOrderByName(UUID tenantId);
}
