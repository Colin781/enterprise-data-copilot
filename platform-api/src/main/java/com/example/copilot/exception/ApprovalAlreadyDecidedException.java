package com.example.copilot.exception;

public class ApprovalAlreadyDecidedException extends RuntimeException {
    public ApprovalAlreadyDecidedException() {
        super("The approval has already been decided.");
    }
}
