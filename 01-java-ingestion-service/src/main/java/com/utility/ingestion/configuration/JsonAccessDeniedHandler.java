package com.utility.ingestion.configuration;

import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.springframework.http.HttpStatus;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.oauth2.server.resource.web.access.BearerTokenAccessDeniedHandler;
import org.springframework.security.web.access.AccessDeniedHandler;

import java.io.IOException;

public class JsonAccessDeniedHandler implements AccessDeniedHandler {

    // Sets 403 and the header WWW-Authenticate: Bearer error="insufficient_scope" ... (RFC 6750), writes no body.
    private final BearerTokenAccessDeniedHandler delegate = new BearerTokenAccessDeniedHandler();

    @Override
    public void handle(HttpServletRequest request, HttpServletResponse response,
                       AccessDeniedException exception) throws IOException, ServletException {
        delegate.handle(request, response, exception);
        JsonErrorWriter.write(request, response, HttpStatus.FORBIDDEN, "The token does not grant the permission this route requires.");
    }
}