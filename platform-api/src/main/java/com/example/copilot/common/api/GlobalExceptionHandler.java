package com.example.copilot.common.api;

import com.example.copilot.common.TraceContext;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.ConstraintViolationException;
import java.util.LinkedHashMap;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingRequestHeaderException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(BadCredentialsException.class)
    ResponseEntity<ApiError> unauthorized(BadCredentialsException exception, HttpServletRequest request) {
        return response(HttpStatus.UNAUTHORIZED, "AUTHENTICATION_FAILED", "Invalid credentials.", request);
    }

    @ExceptionHandler(ResourceNotFoundException.class)
    ResponseEntity<ApiError> notFound(ResourceNotFoundException exception, HttpServletRequest request) {
        return response(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND", exception.getMessage(), request);
    }

    @ExceptionHandler(AccessDeniedException.class)
    ResponseEntity<ApiError> forbidden(AccessDeniedException exception, HttpServletRequest request) {
        return response(
                HttpStatus.FORBIDDEN,
                "ACCESS_DENIED",
                "The caller does not have permission for this operation.",
                request);
    }

    @ExceptionHandler(IdempotencyConflictException.class)
    ResponseEntity<ApiError> conflict(IdempotencyConflictException exception, HttpServletRequest request) {
        return response(HttpStatus.CONFLICT, "IDEMPOTENCY_CONFLICT", exception.getMessage(), request);
    }

    @ExceptionHandler(ApprovalAlreadyDecidedException.class)
    ResponseEntity<ApiError> approvalConflict(ApprovalAlreadyDecidedException exception, HttpServletRequest request) {
        return response(HttpStatus.CONFLICT, "APPROVAL_ALREADY_DECIDED", exception.getMessage(), request);
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    ResponseEntity<ApiError> invalidBody(MethodArgumentNotValidException exception, HttpServletRequest request) {
        var details = new LinkedHashMap<String, Object>();
        exception
                .getBindingResult()
                .getFieldErrors()
                .forEach(error -> details.putIfAbsent(error.getField(), error.getDefaultMessage()));
        var body = new ApiError(
                "VALIDATION_FAILED",
                "The request contains invalid fields.",
                TraceContext.current(request),
                java.time.Instant.now(),
                details);
        return ResponseEntity.status(HttpStatus.UNPROCESSABLE_CONTENT).body(body);
    }

    @ExceptionHandler(ConstraintViolationException.class)
    ResponseEntity<ApiError> invalidParameter(ConstraintViolationException exception, HttpServletRequest request) {
        return response(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED", "A request parameter is invalid.", request);
    }

    @ExceptionHandler({HttpMessageNotReadableException.class, MissingRequestHeaderException.class})
    ResponseEntity<ApiError> malformedRequest(Exception exception, HttpServletRequest request) {
        return response(
                HttpStatus.BAD_REQUEST,
                "MALFORMED_REQUEST",
                "The request is malformed or missing a required value.",
                request);
    }

    @ExceptionHandler(DataIntegrityViolationException.class)
    ResponseEntity<ApiError> duplicateResource(DataIntegrityViolationException exception, HttpServletRequest request) {
        return response(
                HttpStatus.CONFLICT,
                "RESOURCE_CONFLICT",
                "A resource with the same unique value already exists.",
                request);
    }

    @ExceptionHandler(DataSourceHostNotAllowedException.class)
    ResponseEntity<ApiError> dataSourceHostNotAllowed(
            DataSourceHostNotAllowedException exception, HttpServletRequest request) {
        return response(
                HttpStatus.UNPROCESSABLE_CONTENT, "DATA_SOURCE_HOST_NOT_ALLOWED", exception.getMessage(), request);
    }

    @ExceptionHandler(Exception.class)
    ResponseEntity<ApiError> unexpected(Exception exception, HttpServletRequest request) {
        return response(
                HttpStatus.INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "The platform could not complete the request.",
                request);
    }

    private ResponseEntity<ApiError> response(
            HttpStatus status, String code, String message, HttpServletRequest request) {
        return ResponseEntity.status(status).body(ApiError.of(code, message, TraceContext.current(request)));
    }
}
