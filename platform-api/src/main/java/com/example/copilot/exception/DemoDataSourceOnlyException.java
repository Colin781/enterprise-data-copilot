package com.example.copilot.exception;

public class DemoDataSourceOnlyException extends RuntimeException {

    public DemoDataSourceOnlyException() {
        super("This deployment supports only its configured Northwind demonstration source.");
    }
}
