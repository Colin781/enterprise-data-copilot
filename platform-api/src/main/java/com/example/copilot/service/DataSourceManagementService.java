package com.example.copilot.service;

import com.example.copilot.config.properties.DataSourceRegistrationProperties;
import com.example.copilot.dto.request.CreateDataSourceRequest;
import com.example.copilot.dto.response.DataSourceResource;
import com.example.copilot.entity.DataSource;
import com.example.copilot.exception.DataSourceHostNotAllowedException;
import com.example.copilot.exception.DemoDataSourceOnlyException;
import com.example.copilot.repository.DataSourceRepository;
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
        if (!registrationProperties.matches(request)) {
            throw new DemoDataSourceOnlyException();
        }
        if (dataSourceRepository.findAllByTenantIdOrderByName(caller.tenantId()).stream()
                .anyMatch(registrationProperties::matches)) {
            throw new DemoDataSourceOnlyException();
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
                .filter(registrationProperties::matches)
                .map(DataSourceResource::from)
                .toList();
    }
}
