package com.utility.ingestion.configuration;

import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.oauth2.server.resource.web.BearerTokenAuthenticationEntryPoint;
import org.springframework.security.web.AuthenticationEntryPoint;

import java.io.IOException;

public class JsonAuthenticationEntryPoint implements AuthenticationEntryPoint {

    // Spring's own entry point sets the status 401 and the standard challenge header (WWW-Authenticate: Bearer, with
    // error="invalid_token" when a token was sent and was bad). It writes no body. We reuse it and add a body.
    private final BearerTokenAuthenticationEntryPoint delegate = new BearerTokenAuthenticationEntryPoint();

    @Override
    public void commence(HttpServletRequest request, HttpServletResponse response,
                         AuthenticationException exception) throws IOException, ServletException {
        delegate.commence(request, response, exception);
        JsonErrorWriter.write(response, 401, "Unauthorized");
    }
}