package com.utility.ingestion.api;

import com.utility.ingestion.TestData;
import com.utility.ingestion.configuration.SecurityConfiguration;
import com.utility.ingestion.service.IngestionService;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.RequestPostProcessor;

import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.startsWith;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(IngestionController.class)
@Import(SecurityConfiguration.class)       // the real rules, not Spring Boot's default ones
class SecurityRulesTest {

    private static final String URL = "/api/v1/ingest/bulk";
    private static final String INGEST = SecurityConfiguration.INGEST_AUTHORITY;      // "SCOPE_ingest.write"

    // A body the validation rules reject (kwh_value must be above zero), built from the sample the other tests use.
    private static final String INVALID_JSON = TestData.VALID_JSON.replace("\"kwh_value\":12.5", "\"kwh_value\":0");

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private IngestionService ingestionService;     // the controller's collaborator; verifyNoInteractions proves "never reached"

    @MockitoBean
    private JwtDecoder jwtDecoder;                 // required to build the chain; the jwt() post-processor bypasses it

    /**
     * A fake authenticated caller. jwt() puts a ready-made JwtAuthenticationToken into the security context of the
     * request, as if the decoder had verified a real token; the authority is exactly what the test names.
     */
    private static RequestPostProcessor caller(String authority) {
        return jwt().authorities(new SimpleGrantedAuthority(authority));
    }

    @Test
    void noTokenGives401WithAJsonBody() throws Exception {                                     // S01
        mockMvc.perform(post(URL).contentType(MediaType.APPLICATION_JSON).content(TestData.VALID_JSON))
                .andExpect(status().isUnauthorized())
                .andExpect(header().string("WWW-Authenticate", startsWith("Bearer")))       // the standard challenge
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.status").value(401))
                .andExpect(jsonPath("$.title").value("Unauthorized"));
        verifyNoInteractions(ingestionService);        // nothing reached the controller's collaborator
    }

    @Test
    void aTokenWithoutTheScopeGives403WithAJsonBody() throws Exception {                       // S02
        mockMvc.perform(post(URL).contentType(MediaType.APPLICATION_JSON).content(TestData.VALID_JSON)
                        .with(caller("SCOPE_profile")))                                        // authenticated, wrong authority
                .andExpect(status().isForbidden())
                .andExpect(header().string("WWW-Authenticate", containsString("insufficient_scope")))
                .andExpect(jsonPath("$.status").value(403))
                .andExpect(jsonPath("$.title").value("Forbidden"));
        verifyNoInteractions(ingestionService);
    }

    @Test
    void aTokenWithTheScopeReachesTheServiceAndGives200() throws Exception {                   // S03
        when(ingestionService.ingest(any())).thenReturn(TestData.response());

        mockMvc.perform(post(URL).contentType(MediaType.APPLICATION_JSON).content(TestData.VALID_JSON)
                        .with(caller(INGEST)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.metadata.processed_asset").value("MTR-POC2-001"));
    }

    @Test
    void anInvalidBodyWithAGoodTokenStillGives400() throws Exception {                         // S04
        mockMvc.perform(post(URL).contentType(MediaType.APPLICATION_JSON).content(INVALID_JSON)
                        .with(caller(INGEST)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.errors").isArray());
        verifyNoInteractions(ingestionService);
    }

    @Test
    void anInvalidBodyWithoutATokenGives401NotBadRequest() throws Exception {                  // S05
        // Authentication comes before validation (A6): an anonymous caller learns nothing about the rules.
        mockMvc.perform(post(URL).contentType(MediaType.APPLICATION_JSON).content(INVALID_JSON))
                .andExpect(status().isUnauthorized());
        verifyNoInteractions(ingestionService);
    }

    // Three near misses: a different action, a missing suffix, a different case. Authorities are compared exactly.
    @ParameterizedTest(name = "authority {0} is refused")
    @ValueSource(strings = {"SCOPE_ingest.read", "SCOPE_ingest", "SCOPE_INGEST.WRITE"})
    void nearMissScopesGive403(String authority) throws Exception {                            // S06 (3 executions)
        mockMvc.perform(post(URL).contentType(MediaType.APPLICATION_JSON).content(TestData.VALID_JSON)
                        .with(caller(authority)))
                .andExpect(status().isForbidden());
        verifyNoInteractions(ingestionService);
    }

    @Test
    void healthIsNotProtected() throws Exception {                                              // S07
        // This slice contains only IngestionController, so nothing handles /health and the framework answers 404.
        // 404, not 401, is the proof: the security filter let the request through to routing. If /health were
        // protected the answer would be 401 (Break 3 of Part C).
        mockMvc.perform(get("/health")).andExpect(status().isNotFound());
    }

    @Test
    void anUnknownPathIsClosedByDefault() throws Exception {                                    // S08
        // No rule names this path; anyRequest().authenticated() catches it, so it is 401, not a helpful 404.
        mockMvc.perform(get("/api/v1/anything-else")).andExpect(status().isUnauthorized());
    }

    @Test
    void aGetOnTheIngestRouteGives405ForAnAuthorisedCaller() throws Exception {                 // S09
        // The scope rule is written for POST. An authenticated GET passes security and Spring MVC says "not allowed".
        mockMvc.perform(get(URL).with(caller(INGEST))).andExpect(status().isMethodNotAllowed());
    }

    @Test
    void aUrlTheFirewallRejectsGives400AsProblemDetails() throws Exception {                   // C15, D44 (URL half)
        // StrictHttpFirewall refuses a semicolon in the path before any filter or controller runs; the
        // RequestRejectedHandler bean of SecurityConfiguration writes the answer.
        mockMvc.perform(post(URL + ";x=1").contentType(MediaType.APPLICATION_JSON).content(TestData.VALID_JSON)
                        .with(caller(INGEST)))
                .andExpect(status().isBadRequest())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON));
        verifyNoInteractions(ingestionService);
    }
}
