package com.utility.ingestion.api;

import com.utility.ingestion.TestData;
import com.utility.ingestion.api.dto.BulkIngestionRequest;
import com.utility.ingestion.service.IngestionService;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.web.client.HttpClientErrorException;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(IngestionController.class)
class IngestionControllerTest {

    private static final String URL = "/api/v1/ingest/bulk";

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private IngestionService ingestionService;

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
                .andExpect(jsonPath("$.status").value(400))
                .andExpect(jsonPath("$.error").value("Validation failed"))
                .andExpect(jsonPath("$.timestamp").exists())
                // Finding D22: the keys are Java property names, not the JSON names the client sent (Stage 6 flips this).
                .andExpect(jsonPath("$.details.meterId").exists())
                .andExpect(jsonPath("$.details['readings[0].voltage']").exists());

        verify(ingestionService, never()).ingest(any());
    }

    @Test
    void malformedJsonIsRejectedWith400() throws Exception {
        mockMvc.perform(post(URL).contentType(MediaType.APPLICATION_JSON).content("{\"meter_id\": "))
                .andExpect(status().isBadRequest());
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
                .andExpect(status().isUnsupportedMediaType());
    }

    @Test
    void theRouteAcceptsPostOnly() throws Exception {
        mockMvc.perform(get(URL)).andExpect(status().isMethodNotAllowed());
    }

    @Test
    void documentsD3_aFailureOfTheDownstreamHasNoHandler() {
        // Finding D3 (downstream half): ApiExceptionHandler handles validation errors only. An exception from the
        // downstream call therefore propagates unhandled; in the running application Spring turns it into a generic
        // 500. Stage 6 adds a handler that answers 502, and this test is then changed to expect that.
        when(ingestionService.ingest(any(BulkIngestionRequest.class))).thenThrow(
                HttpClientErrorException.create(HttpStatus.UNPROCESSABLE_ENTITY, "Unprocessable",
                        HttpHeaders.EMPTY, new byte[0], null));

        assertThatThrownBy(() -> mockMvc.perform(
                post(URL).contentType(MediaType.APPLICATION_JSON).content(TestData.VALID_JSON)))
                .hasRootCauseInstanceOf(HttpClientErrorException.class);
    }
}
