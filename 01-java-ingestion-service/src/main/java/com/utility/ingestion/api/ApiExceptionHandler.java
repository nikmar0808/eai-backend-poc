package com.utility.ingestion.api;

import com.fasterxml.jackson.core.JsonParseException;
import com.fasterxml.jackson.databind.JsonMappingException;
import com.utility.ingestion.configuration.JsonRequestRejectedHandler;
import jakarta.servlet.http.HttpServletRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.ProblemDetail;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.security.web.firewall.RequestRejectedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.context.request.ServletWebRequest;
import org.springframework.web.context.request.WebRequest;
import org.springframework.web.servlet.mvc.method.annotation.ResponseEntityExceptionHandler;

import java.net.SocketTimeoutException;
import java.net.URI;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Every error that passes through Spring MVC becomes an RFC 9457 problem-details body (application/problem+json).
 * The base class already does so for Spring's own exceptions (404, 405, 415, ...); this class adds the field list for
 * the two kinds of 400, and maps the failures of the call to python-validator to 502 and 504 (finding D3).
 * The 401 and 403 answers are produced earlier, in the security filters (JsonErrorWriter).
 */
@RestControllerAdvice
public class ApiExceptionHandler extends ResponseEntityExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(ApiExceptionHandler.class);

    // ---- 400: a rule is broken (Bean Validation) -------------------------------------------------------------------

    @Override
    protected ResponseEntity<Object> handleMethodArgumentNotValid(
            MethodArgumentNotValidException exception, HttpHeaders headers, HttpStatusCode status, WebRequest request) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST, "The request body failed validation.");
        // One entry per broken rule. getField() is the JAVA path (meterId, readings[0].kwhValue); jsonName() turns it
        // into the name the client sent (meter_id, readings[0].kwh_value), which closes finding D22.
        problem.setProperty("errors", exception.getBindingResult().getFieldErrors().stream()
                .map(error -> Map.of(
                        "field", jsonName(error.getField()),
                        "message", String.valueOf(error.getDefaultMessage())))
                .toList());
        return handleExceptionInternal(exception, problem, headers, HttpStatus.BAD_REQUEST, request);
    }

    // ---- 400: the body cannot be read (malformed JSON, a value of the wrong type, a bad timestamp) ------------------

    @Override
    protected ResponseEntity<Object> handleHttpMessageNotReadable(
            HttpMessageNotReadableException exception, HttpHeaders headers, HttpStatusCode status, WebRequest request) {
        Throwable cause = exception.getCause();
        ProblemDetail problem;
        if (cause instanceof JsonMappingException mapping && !mapping.getPath().isEmpty()) {
            // Well-formed JSON with a value that cannot become the declared type (D29: a number for a timestamp; D37:
            // an offset beyond +-14:00). The path names the field; the exception message is NOT used, because Jackson
            // copies the offending input value into it.
            problem = ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST, "A value in the request body has the wrong type or format.");
            problem.setProperty("errors", List.of(Map.of("field", jsonPath(mapping), "message", "has the wrong type or format")));
        } else if (cause instanceof JsonParseException) {
            problem = ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST, "The request body is not well-formed JSON.");
        } else {
            problem = ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST, "The request body could not be read.");
        }
        return handleExceptionInternal(exception, problem, headers, HttpStatus.BAD_REQUEST, request);
    }

    // ---- 502 and 504: the call to python-validator failed (finding D3) ----------------------------------------------

    /** Python answered 4xx or 5xx. To the client the gateway IS the API, so this is the gateway's failure: 502. */
    @ExceptionHandler(RestClientResponseException.class)
    public ProblemDetail handleDownstreamAnswer(RestClientResponseException exception, HttpServletRequest request) {
        // The status only. Python's body is neither logged nor returned: a 422 body echoes the client's input.
        log.warn("python-validator answered {}; answering 502", exception.getStatusCode().value());
        return problem(HttpStatus.BAD_GATEWAY, "python-validator rejected the request or failed.", request);
    }

    /**
     * No usable answer from python-validator: a refused or reset connection, no answer within the read timeout of
     * Stage 1A, or an answer that cannot be read. RestClient reports a failure while SENDING as ResourceAccessException
     * and a failure while READING the answer (the usual case with the simple client) as a plain RestClientException;
     * the handler takes their common parent. RestClientResponseException (Python answered 4xx or 5xx) is a more
     * specific subclass and still goes to handleDownstreamAnswer.
     */
    @ExceptionHandler(RestClientException.class)
    public ProblemDetail handleDownstreamUnavailable(RestClientException exception, HttpServletRequest request) {
        if (causedBy(exception, SocketTimeoutException.class)) {
            log.warn("python-validator did not answer in time; answering 504");
            return problem(HttpStatus.GATEWAY_TIMEOUT, "python-validator did not answer in time.", request);
        }
        log.warn("python-validator gave no usable answer ({}); answering 502", rootCause(exception).getClass().getSimpleName());
        return problem(HttpStatus.BAD_GATEWAY, "python-validator could not be reached or gave no usable answer.", request);
    }

    // ---- 400: Spring Security's firewall refused a header (finding D44) --------------------------------------------

    /**
     * The firewall checks a header's value when the application first reads it. Reading the JSON body copies every
     * header, so a header with a disallowed character is rejected inside Spring MVC and arrives here. Without this
     * handler it fell to handleUnexpected and became a 500. The exception message is not used: it quotes the value.
     */
    @ExceptionHandler(RequestRejectedException.class)
    public ProblemDetail handleRequestRejected(RequestRejectedException exception, HttpServletRequest request) {
        log.warn("Request rejected by the firewall; answering 400");
        return problem(HttpStatus.BAD_REQUEST, JsonRequestRejectedHandler.REJECTED_DETAIL, request);
    }
    
    // ---- 500: anything else ----------------------------------------------------------------------------------------

    @ExceptionHandler(Exception.class)
    public ProblemDetail handleUnexpected(Exception exception, HttpServletRequest request) {
        // The stack trace goes to the log (the gateway holds no SQL); the client gets a fixed sentence.
        log.error("Unexpected error; answering 500", exception);
        return problem(HttpStatus.INTERNAL_SERVER_ERROR, "An unexpected error occurred.", request);
    }

    // ---- helpers ---------------------------------------------------------------------------------------------------

    /** Spring's own problem bodies have no instance; set it to the request path for every one of them. */
    @Override
    protected ResponseEntity<Object> handleExceptionInternal(
            Exception exception, Object body, HttpHeaders headers, HttpStatusCode statusCode, WebRequest request) {
        ResponseEntity<Object> response = super.handleExceptionInternal(exception, body, headers, statusCode, request);
        if (response != null && response.getBody() instanceof ProblemDetail problem && problem.getInstance() == null
                && request instanceof ServletWebRequest servlet) {
            problem.setInstance(URI.create(servlet.getRequest().getRequestURI()));
        }
        return response;
    }

    private static ProblemDetail problem(HttpStatus status, String detail, HttpServletRequest request) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(status, detail);   // title = the status's reason phrase
        problem.setInstance(URI.create(request.getRequestURI()));
        return problem;
    }

    /** meterId -> meter_id; readings[0].kwhValue -> readings[0].kwh_value (every JSON name here is snake_case). */
    static String jsonName(String javaPath) {
        return javaPath.replaceAll("([a-z0-9])([A-Z])", "$1_$2").toLowerCase(Locale.ROOT);
    }

    /** Jackson's path, already in JSON names: readings, [0], timestamp -> readings[0].timestamp */
    static String jsonPath(JsonMappingException exception) {
        StringBuilder path = new StringBuilder();
        for (JsonMappingException.Reference reference : exception.getPath()) {
            if (reference.getFieldName() != null) {
                if (!path.isEmpty()) {
                    path.append('.');
                }
                path.append(reference.getFieldName());
            } else if (reference.getIndex() >= 0) {
                path.append('[').append(reference.getIndex()).append(']');
            }
        }
        return path.toString();
    }

    /** The innermost cause, for the log: SocketException, ConnectException, ... (its class name only, never its text). */
    private static Throwable rootCause(Throwable throwable) {
        Throwable current = throwable;
        while (current.getCause() != null && current.getCause() != current) {
            current = current.getCause();
        }
        return current;
    }
    
    private static boolean causedBy(Throwable throwable, Class<? extends Throwable> type) {
        for (Throwable current = throwable; current != null; current = current.getCause()) {
            if (type.isInstance(current)) {
                return true;
            }
        }
        return false;
    }
}
