package com.example.copilot.repository;

import com.example.copilot.entity.DataSource;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface DataSourceRepository extends JpaRepository<DataSource, UUID> {
    Optional<DataSource> findByIdAndTenantIdAndEnabledTrue(UUID id, UUID tenantId);

    List<DataSource> findAllByTenantIdOrderByName(UUID tenantId);
}
