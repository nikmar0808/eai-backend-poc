package com.utility.ingestion.configuration;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.security.web.firewall.RequestRejectedException;
import org.springframework.security.web.firewall.RequestRejectedHandler;

import java.io.IOException;

/**
 * Spring Security's firewall (StrictHttpFirewall) refuses a request whose URL contains a character it does not allow
 * (a semicolon, an encoded slash, "//") before any filter or controller runs. This handler answers 400 problem details,
 * the same body ApiExceptionHandler gives when the firewall refuses a header inside Spring MVC (finding D44).
 * It is used because SecurityConfiguration declares it as a bean.
 */
public class JsonRequestRejectedHandler implements RequestRejectedHandler {

    /** Shared with ApiExceptionHandler. A fixed sentence: the exception message quotes the offending value (A7). */
    public static final String REJECTED_DETAIL = "The request was refused: its method, URL or a header contains something that is not allowed.";

    private static final Logger log = LoggerFactory.getLogger(JsonRequestRejectedHandler.class);

    @Override
    public void handle(HttpServletRequest request, HttpServletResponse response,
                       RequestRejectedException exception) throws IOException {
        log.warn("Request rejected by the firewall; answering 400");
        JsonErrorWriter.write(request, response, HttpStatus.BAD_REQUEST, REJECTED_DETAIL);
    }
}