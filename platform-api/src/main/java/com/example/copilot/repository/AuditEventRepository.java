package com.example.copilot.repository;

import com.example.copilot.entity.AuditEvent;
import java.util.List;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface AuditEventRepository extends JpaRepository<AuditEvent, UUID> {
    List<AuditEvent> findAllByTenantIdOrderByCreatedAtDesc(UUID tenantId);

    long countByTenantIdAndAction(UUID tenantId, String action);
}
