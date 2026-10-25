package com.utility.ingestion.api;

import com.utility.ingestion.TestData;
import com.utility.ingestion.api.dto.BulkIngestionRequest;
import com.utility.ingestion.service.IngestionService;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.ResourceAccessException;

import com.utility.ingestion.configuration.JsonRequestRejectedHandler;
import com.utility.ingestion.configuration.SecurityConfiguration;
import com.utility.ingestion.configuration.JsonStrictnessConfiguration;
import org.springframework.context.annotation.Import;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.test.context.support.WithMockUser;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.net.ConnectException;
import java.net.SocketTimeoutException;
import java.nio.charset.StandardCharsets;

import static org.hamcrest.Matchers.hasItems;
import static org.hamcrest.Matchers.not;
import static org.hamcrest.Matchers.containsString;


@WebMvcTest(IngestionController.class)
// The slice does not scan @Configuration classes, so the real rules are imported explicitly: these tests then run
// behind the same security as production, and fail if the scope is not supplied.
@Import({SecurityConfiguration.class, JsonStrictnessConfiguration.class})
// Every test in the class acts as an authenticated caller holding the ingest scope. (@WithMockUser puts an
// Authentication with these authorities into the security context of each test; the rules of S01 to S09 are tested
// in their own class.)
@WithMockUser(authorities = "SCOPE_ingest.write")
class IngestionControllerTest {

    private static final String URL = "/api/v1/ingest/bulk";

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private IngestionService ingestionService;

    @MockitoBean                     // the resource-server configuration requires a JwtDecoder bean; its behaviour is not used here
    private JwtDecoder jwtDecoder;


    @Test
    void aValidRequestIsPassedToTheServiceAndTheResponseIsReturnedAsJson() throws Exception {
        when(ingestionService.ingest(any(BulkIngestionRequest.class))).thenReturn(TestData.response());

        mockMvc.perform(post(URL).contentType(MediaType.APPLICATION_JSON).content(TestData.VALID_JSON))
                .andExpect(status().isOk())
                // Finding D5 (text/plain) is fixed: this assertion guards against its return.
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.message").value("ok"))
                .andExpect(jsonPath("$.metadata.intervals_saved").value(1))
                .andExpect(jsonPath("$.analytics_summary.cumulative_kwh").value(12.5));

        ArgumentCaptor<BulkIngestionRequest> captor = ArgumentCaptor.forClass(BulkIngestionRequest.class);
        verify(ingestionService).ingest(captor.capture());
        assertThat(captor.getValue().meterId()).isEqualTo("MTR-POC2-001");
        assertThat(captor.getValue().readings()).hasSize(1);
    }

    @Test
    void anInvalidRequestIsRejectedWith400AndAStructuredBodyAndNeverReachesTheService() throws Exception {
        String invalid = """
                {"meter_id":"M1","grid_zone":"ZONE-A",
                 "readings":[{"timestamp":"2026-10-09T00:00:00Z","kwh_value":12.5,"voltage":50.0}]}
                """;

        mockMvc.perform(post(URL).contentType(MediaType.APPLICATION_JSON).content(invalid))
                .andExpect(status().isBadRequest())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.status").value(400))
                .andExpect(jsonPath("$.title").value("Bad Request"))
                .andExpect(jsonPath("$.instance").value("/api/v1/ingest/bulk"))
                // Finding D22 closed: the fields are named as the client sent them.
                .andExpect(jsonPath("$.errors[*].field", hasItems("meter_id", "readings[0].voltage")));

        verify(ingestionService, never()).ingest(any());
    }

    @Test
    void malformedJsonIsRejectedWith400() throws Exception {
        mockMvc.perform(post(URL).contentType(MediaType.APPLICATION_JSON).content("{\"meter_id\": "))
                .andExpect(status().isBadRequest())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))   // D35 closed
                .andExpect(jsonPath("$.detail").value("The request body is not well-formed JSON."));
        verify(ingestionService, never()).ingest(any());
    }

    @Test
    void aTimestampWithoutAnOffsetIsRejectedWith400() throws Exception {
        String naive = TestData.VALID_JSON.replace("2026-10-09T00:00:00Z", "2026-10-09T00:00:00");

        mockMvc.perform(post(URL).contentType(MediaType.APPLICATION_JSON).content(naive))
                .andExpect(status().isBadRequest());
        verify(ingestionService, never()).ingest(any());
    }

    @Test
    void aBodyThatIsNotJsonIsRejectedWith415() throws Exception {
        mockMvc.perform(post(URL).contentType(MediaType.TEXT_PLAIN).content(TestData.VALID_JSON))
                .andExpect(status().isUnsupportedMediaType())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON));
    }

    @Test
    void theRouteAcceptsPostOnly() throws Exception {
        mockMvc.perform(get(URL)).andExpect(status().isMethodNotAllowed());
    }

    @Test
    void aRejectionByTheDownstreamGives502WithoutItsBody() throws Exception {                 // C08, D3
        // A 422 body as Python sends it: it echoes the client's input. A recognisable value is planted in it, and the
        // test asserts that it never reaches the client (A7).
        byte[] pythonBody = "{\"detail\":[{\"input\":\"SECRET-INPUT-VALUE\"}]}".getBytes(StandardCharsets.UTF_8);
        when(ingestionService.ingest(any(BulkIngestionRequest.class))).thenThrow(
                HttpClientErrorException.create(HttpStatus.UNPROCESSABLE_ENTITY, "Unprocessable",
                        HttpHeaders.EMPTY, pythonBody, StandardCharsets.UTF_8));

        mockMvc.perform(post(URL).contentType(MediaType.APPLICATION_JSON).content(TestData.VALID_JSON))
                .andExpect(status().isBadGateway())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.title").value("Bad Gateway"))
                .andExpect(content().string(not(containsString("SECRET-INPUT-VALUE"))));
    }

    @Test
    void aNumberAsTimestampIsRejectedWith400AndNamesTheField() throws Exception {              // C01, D29
        String numeric = TestData.VALID_JSON.replace("\"2026-10-09T00:00:00Z\"", "0");

        mockMvc.perform(post(URL).contentType(MediaType.APPLICATION_JSON).content(numeric))
                .andExpect(status().isBadRequest())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.errors[0].field").value("readings[0].timestamp"));
        verify(ingestionService, never()).ingest(any());
    }

    @ParameterizedTest(name = "offset {0} is refused")
    @ValueSource(strings = {"+14:30", "-15:00", "+19:00"})
    void anOffsetBeyondFourteenHoursIsRejectedWith400(String offset) throws Exception {        // C02, D37 (3)
        // +14:30 and -15:00 are valid for Java and for RFC 3339; +19:00 is beyond what Java can even represent.
        String body = TestData.VALID_JSON.replace("2026-10-09T00:00:00Z", "2026-10-09T00:00:00" + offset);

        mockMvc.perform(post(URL).contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.errors[0].field").value("readings[0].timestamp"));
        verify(ingestionService, never()).ingest(any());
    }

    @Test
    void anOffsetOfExactlyFourteenHoursIsAccepted() throws Exception {                        // C07, boundary
        when(ingestionService.ingest(any(BulkIngestionRequest.class))).thenReturn(TestData.response());
        String body = TestData.VALID_JSON.replace("2026-10-09T00:00:00Z", "2026-10-09T00:00:00+14:00");

        mockMvc.perform(post(URL).contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isOk());
    }

    @Test
    void aNullReadingIsRejectedWith400() throws Exception {                                    // C03, D36
        String body = "{\"meter_id\":\"MTR-POC2-001\",\"grid_zone\":\"ZONE-A\",\"readings\":[null]}";

        mockMvc.perform(post(URL).contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.errors[*].field", hasItems("readings[0]")));
        verify(ingestionService, never()).ingest(any());
    }

    @ParameterizedTest(name = "a control character in {0} is refused")
    @ValueSource(strings = {"grid_zone", "meter_id"})
    void aControlCharacterInAnIdentifierIsRejectedWith400(String field) throws Exception {     // C04, D39 (2)
        // In Java source "\\u0000" is backslash-u-0000, the JSON escape for NUL; Jackson turns it into U+0000.
        String body = field.equals("grid_zone")
                ? TestData.VALID_JSON.replace("\"ZONE-A\"", "\"ZONE\\u0000A\"")
                : TestData.VALID_JSON.replace("\"MTR-POC2-001\"", "\"MTR\\u0001POC2\"");

        mockMvc.perform(post(URL).contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.errors[*].field", hasItems(field)));
        verify(ingestionService, never()).ingest(any());
    }

    @Test
    void aDownstreamTimeoutGives504() throws Exception {                                       // C05, D3
        // What RestClient throws when the read timeout of Stage 1A expires.
        when(ingestionService.ingest(any(BulkIngestionRequest.class))).thenThrow(
                new ResourceAccessException("I/O error", new SocketTimeoutException("Read timed out")));

        mockMvc.perform(post(URL).contentType(MediaType.APPLICATION_JSON).content(TestData.VALID_JSON))
                .andExpect(status().isGatewayTimeout())
                .andExpect(jsonPath("$.title").value("Gateway Timeout"));
    }

    @Test
    void anUnreachableDownstreamGives502() throws Exception {                                  // C06, D3
        when(ingestionService.ingest(any(BulkIngestionRequest.class))).thenThrow(
                new ResourceAccessException("I/O error", new ConnectException("Connection refused")));

        mockMvc.perform(post(URL).contentType(MediaType.APPLICATION_JSON).content(TestData.VALID_JSON))
                .andExpect(status().isBadGateway());
    }

    @Test
    void anUnexpectedErrorGives500WithoutItsMessage() throws Exception {                       // C11, A6 last row, A7
        // A failure nobody planned for. Its message is planted with a recognisable value, which must not reach the client.
        when(ingestionService.ingest(any(BulkIngestionRequest.class)))
                .thenThrow(new IllegalStateException("SECRET-INTERNAL-STATE"));

        mockMvc.perform(post(URL).contentType(MediaType.APPLICATION_JSON).content(TestData.VALID_JSON))
                .andExpect(status().isInternalServerError())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.detail").value("An unexpected error occurred."))
                .andExpect(content().string(not(containsString("SECRET-INTERNAL-STATE"))));
    }

    @Test
    void aMissingBodyIsRejectedWith400AsProblemDetails() throws Exception {                    // C12, D35
        // No body at all: Spring reports "Required request body is missing" with no cause, the third branch.
        mockMvc.perform(post(URL).contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isBadRequest())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.detail").value("The request body could not be read."));
        verify(ingestionService, never()).ingest(any());
    }


    @Test
    void aHeaderWithAControlCharacterGives400NotAServerError() throws Exception {             // C13, D44 (header half)
        // The firewall checks a header's value when it is first read; reading the JSON body copies every header, so the
        // rejection happens inside Spring MVC. 0x97 is a C1 control character, built with a cast, not a Java escape.
        String value = "note" + (char) 0x97;

        mockMvc.perform(post(URL).contentType(MediaType.APPLICATION_JSON).content(TestData.VALID_JSON)
                        .header("X-Client-Note", value))
                .andExpect(status().isBadRequest())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.detail").value(JsonRequestRejectedHandler.REJECTED_DETAIL));
        verify(ingestionService, never()).ingest(any());
    }

    @Test
    void aNonAsciiCharacterInAnIdentifierIsRejectedWith400() throws Exception {               // C14, D45
        // U+1F600 lies above U+FFFF: one character for JSON Schema and Python, two UTF-16 code units for @Size.
        // Identifiers are printable ASCII, so all three agree that it is refused.
        String emoji = new String(Character.toChars(0x1F600));
        String body = TestData.VALID_JSON.replace("\"MTR-POC2-001\"", "\"MTR-" + emoji + "-01\"");

        mockMvc.perform(post(URL).contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.errors[*].field", hasItems("meter_id")));
        verify(ingestionService, never()).ingest(any());
    }

    @ParameterizedTest(name = "{0} of the wrong JSON type is refused")
    @ValueSource(strings = {"grid_zone", "meter_id", "readings[0].kwh_value"})
    void aValueOfTheWrongJsonTypeIsRejectedWith400(String field) throws Exception {          // C16, D48 (3)
        // Without JsonStrictnessConfiguration, Jackson would accept all three: false and 1234567 as the text "false"
        // and "1234567", and "12.5" as the number 12.5.
        String body = switch (field) {
            case "grid_zone" -> TestData.VALID_JSON.replace("\"ZONE-A\"", "false");
            case "meter_id" -> TestData.VALID_JSON.replace("\"MTR-POC2-001\"", "1234567");
            default -> TestData.VALID_JSON.replace("12.5", "\"12.5\"");
        };

        mockMvc.perform(post(URL).contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isBadRequest())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.errors[0].field").value(field));
        verify(ingestionService, never()).ingest(any());
    }
}
