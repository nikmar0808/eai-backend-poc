package com.utility.ingestion.configuration;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;

@Configuration
@EnableWebSecurity     // switches on Spring Security's servlet filter in front of Spring MVC
public class SecurityConfiguration {

    /** Spring prefixes every scope with "SCOPE_" when it turns the scope claim into authorities. */
    public static final String INGEST_AUTHORITY = "SCOPE_ingest.write";

    // A SecurityFilterChain is "the ordered list of security filters for the requests that match". There is one.
    @Bean
    public SecurityFilterChain apiSecurity(HttpSecurity http) throws Exception {
        http
            // CSRF protects browsers that authenticate with a cookie the browser adds by itself. This API is
            // authenticated only by a header the caller adds on purpose, so there is nothing to forge. Leaving it
            // on would refuse every POST that has no CSRF token.
            .csrf(AbstractHttpConfigurer::disable)
            // No HTTP session is created or used: each request stands alone (stateless).
            .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            // The rules are tried top to bottom; the first that matches decides.
            .authorizeHttpRequests(rules -> rules
                // Docker's health check carries no token (Break 3 of Part C shows what happens otherwise).
                .requestMatchers(HttpMethod.GET, "/health").permitAll()
                // The generated API document. It is switched off unless asked (Stage 2, T38); when on, it is not secret.
                .requestMatchers(HttpMethod.GET, "/v3/api-docs/**").permitAll()
                // Spring Boot forwards unhandled errors internally to /error to build the body. That forward passes
                // the security rules again; without this line an anonymous caller's 404 or 500 became a 401.
                // Safe: the original request's own rule has already been applied.
                .requestMatchers("/error").permitAll()
                // The permission: POST on the ingest routes needs exactly this authority.
                .requestMatchers(HttpMethod.POST, "/api/v1/ingest/**").hasAuthority(INGEST_AUTHORITY)
                // Everything else must at least be authenticated. A route added next year is closed until opened.
                .anyRequest().authenticated())
            // Accept "Authorization: Bearer <jwt>", verified by the JwtDecoder bean. The two handlers shape the
            // 401 (no or bad token) and 403 (good token, wrong authority) answers.
            .oauth2ResourceServer(oauth -> oauth
                .jwt(Customizer.withDefaults())
                .authenticationEntryPoint(new JsonAuthenticationEntryPoint())
                .accessDeniedHandler(new JsonAccessDeniedHandler()));
        return http.build();
    }
}