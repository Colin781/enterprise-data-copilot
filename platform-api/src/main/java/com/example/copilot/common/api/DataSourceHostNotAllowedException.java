package com.example.copilot.common.api;

public class DataSourceHostNotAllowedException extends RuntimeException {

    public DataSourceHostNotAllowedException() {
        super("The data source host is not available in this deployment.");
    }
}
