package com.example.copilot.service;

import com.example.copilot.dto.request.AnalysisJobSearchRequest;
import com.example.copilot.dto.response.AnalysisJobSearchItem;
import com.example.copilot.dto.response.AnalysisJobSearchPage;
import com.example.copilot.mapper.AnalysisJobQueryScope;
import com.example.copilot.mapper.AnalysisJobSearchMapper;
import com.example.copilot.security.CallerIdentity.Caller;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Objects;
import java.util.Set;

@Service
public class AnalysisJobQueryService {

    private static final Set<String> READ_ROLES =
            Set.of("ADMIN", "ANALYST", "VIEWER");

    private final AnalysisJobSearchMapper mapper;

    public AnalysisJobQueryService(AnalysisJobSearchMapper mapper) {
        this.mapper = mapper;
    }

    @Transactional(
            readOnly = true,
            isolation = Isolation.REPEATABLE_READ)
    public AnalysisJobSearchPage search(
            AnalysisJobSearchRequest request,
            Caller caller) {

        Objects.requireNonNull(request, "request is required");
        Objects.requireNonNull(caller, "caller is required");

        if (caller.roles().stream().noneMatch(READ_ROLES::contains)){
            throw new AccessDeniedException(
                    "The caller cannot search analysis jobs");
        }

        var ownerId = caller.roles().contains("ADMIN")
                ? null
                : caller.userId();

        var scope = new AnalysisJobQueryScope(
                caller.tenantId(),
                ownerId,
                request.dataSourceId());

        long total = mapper.count(scope, request.criteria());

        List<AnalysisJobSearchItem> items = total ==0
                ? List.of()
                : mapper.findPage(
                        scope,
                        request.criteria(),
                        request.offset(),
                        request.size());

        long totalPage = total / request.size()
                + (total % request.size() == 0 ? 0 : 1);

        return new AnalysisJobSearchPage(
                items,
                total,
                request.page(),
                request.size(),
                totalPage);
    }
}
