package com.example.copilot.identity.repository;

import com.example.copilot.identity.domain.AppUser;
import jakarta.persistence.LockModeType;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;

public interface AppUserRepository extends JpaRepository<AppUser, UUID> {
    Optional<AppUser> findByTenantIdAndEmailIgnoreCase(UUID tenantId, String email);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    Optional<AppUser> findByIdAndTenantId(UUID id, UUID tenantId);
}
