package com.example.copilot.mapper;

import com.example.copilot.dto.request.AnalysisJobSearchCriteria;
import com.example.copilot.dto.response.AnalysisJobQueryRow;
import java.util.List;
import java.util.UUID;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface AnalysisJobQueryMapper {

    AnalysisJobQueryRow findByTenantIdAndId(
            @Param("tenantId") UUID tenantId,
            @Param("jobId") UUID jobId);

    List<AnalysisJobQueryRow> search(
            @Param("tenantId") UUID tenantId,
            @Param("criteria") AnalysisJobSearchCriteria criteria);
}