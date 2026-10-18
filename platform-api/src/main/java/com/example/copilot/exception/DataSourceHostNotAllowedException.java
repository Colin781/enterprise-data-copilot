package com.example.copilot.exception;

public class DataSourceHostNotAllowedException extends RuntimeException {

    public DataSourceHostNotAllowedException() {
        super("The data source host is not available in this deployment.");
    }
}
