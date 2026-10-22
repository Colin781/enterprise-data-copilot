package com.example.copilot.mapper;

import com.example.copilot.dto.request.AnalysisJobSearchCriteria;
import com.example.copilot.dto.response.AnalysisJobSearchItem;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface AnalysisJobSearchMapper {

    long count(
            @Param("scope") AnalysisJobQueryScope scope,
            @Param("criteria")AnalysisJobSearchCriteria criteria);


    List<AnalysisJobSearchItem> findPage(
            @Param("scope") AnalysisJobQueryScope scope,
            @Param("criteria") AnalysisJobSearchCriteria criteria,
            @Param("offset") long offset,
            @Param("limit") int limit);
}

