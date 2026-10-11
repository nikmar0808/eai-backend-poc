package com.utility.ingestion.api.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.Size;

import java.util.List;

public record BulkIngestionRequest(
        @JsonProperty("meter_id")
        @NotBlank(message = "Meter ID cannot be blank")
        @Size(min = 5, max = 20, message = "Meter ID must be between 5 and 20 characters")
        String meterId,

        @JsonProperty("grid_zone")
        @NotBlank(message = "Grid Zone cannot be blank")
        @Size(max = 50, message = "Grid Zone must be at most 50 characters")
        String gridZone,

        @NotEmpty(message = "Readings array cannot be empty")
        @Size(max = 1000, message = "At most 1000 readings per request")
        @Valid
        List<MeterReadingRequest> readings
) {
}
