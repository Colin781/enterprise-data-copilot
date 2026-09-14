package com.example.copilot.identity.repository;

import com.example.copilot.identity.domain.Tenant;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface TenantRepository extends JpaRepository<Tenant, UUID> {
    Optional<Tenant> findBySlugAndEnabledTrue(String slug);
}
