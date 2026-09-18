package com.example.copilot.common.api;

public class ApprovalAlreadyDecidedException extends RuntimeException {
    public ApprovalAlreadyDecidedException() {
        super("The approval has already been decided.");
    }
}
