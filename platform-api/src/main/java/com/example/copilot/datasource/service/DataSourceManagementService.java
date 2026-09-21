package com.example.copilot.datasource.service;

import com.example.copilot.audit.service.AuditService;
import com.example.copilot.common.api.DataSourceHostNotAllowedException;
import com.example.copilot.datasource.api.CreateDataSourceRequest;
import com.example.copilot.datasource.api.DataSourceResource;
import com.example.copilot.datasource.domain.DataSource;
import com.example.copilot.datasource.repository.DataSourceRepository;
import com.example.copilot.security.CallerIdentity.Caller;
import java.util.List;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class DataSourceManagementService {

    private final DataSourceRepository dataSourceRepository;
    private final AuditService auditService;
    private final DataSourceRegistrationProperties registrationProperties;

    public DataSourceManagementService(
            DataSourceRepository dataSourceRepository,
            AuditService auditService,
            DataSourceRegistrationProperties registrationProperties) {
        this.dataSourceRepository = dataSourceRepository;
        this.auditService = auditService;
        this.registrationProperties = registrationProperties;
    }

    @Transactional
    public DataSourceResource create(CreateDataSourceRequest request, Caller caller, String traceId) {
        if (!registrationProperties.allows(request.host())) {
            throw new DataSourceHostNotAllowedException();
        }
        var dataSource = dataSourceRepository.save(new DataSource(
                UUID.randomUUID(),
                caller.tenantId(),
                request.name().trim(),
                request.host().trim(),
                request.port(),
                request.databaseName().trim(),
                request.allowedSchema(),
                request.secretRef()));
        auditService.recordSuccess(
                caller.tenantId(), caller.userId(), "DATA_SOURCE_CREATED", "DATA_SOURCE", dataSource.getId(), traceId);
        return DataSourceResource.from(dataSource);
    }

    @Transactional(readOnly = true)
    public List<DataSourceResource> list(Caller caller) {
        return dataSourceRepository.findAllByTenantIdOrderByName(caller.tenantId()).stream()
                .map(DataSourceResource::from)
                .toList();
    }
}
