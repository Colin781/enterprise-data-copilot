package com.example.copilot.repository;

import com.example.copilot.entity.MetricDocument;
import java.util.List;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface MetricDocumentRepository extends JpaRepository<MetricDocument, UUID> {
    List<MetricDocument> findTop100ByTenantIdOrderByUpdatedAtDesc(UUID tenantId);
}
