package com.example.copilot.common.api;

public class DemoDataSourceOnlyException extends RuntimeException {

    public DemoDataSourceOnlyException() {
        super("This deployment supports only its configured Northwind demonstration source.");
    }
}
