package com.utility.ingestion.api.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import java.util.List;

public record BulkIngestionRequest(
        @JsonProperty("meter_id")
        @NotBlank(message = "Meter ID cannot be blank")
        @Size(min = 5, max = 20, message = "Meter ID must be between 5 and 20 characters")
        // Printable ASCII only, no spaces (findings D39, D45): no control characters (PostgreSQL text cannot store NUL),
        // and one character is one UTF-16 code unit, so @Size, the contract's maxLength and Python's len() agree.
        @Pattern(regexp = "^[\\x21-\\x7E]+$", message = "Meter ID must contain printable ASCII characters only, no spaces")
        String meterId,

        @JsonProperty("grid_zone")
        @NotBlank(message = "Grid Zone cannot be blank")
        @Size(max = 50, message = "Grid Zone must be at most 50 characters")
        // Printable ASCII (spaces allowed) with at least one visible character (findings D39, D45).
        @Pattern(regexp = "^[\\x20-\\x7E]*[\\x21-\\x7E][\\x20-\\x7E]*$",
                message = "Grid Zone must contain printable ASCII characters only, at least one of them visible")
        String gridZone,

        @NotEmpty(message = "Readings array cannot be empty")
        @Size(max = 1000, message = "At most 1000 readings per request")
        // Container-element constraints: @NotNull applies to EACH element, so [null] is refused (finding D36);
        // @Valid on the element type replaces the old @Valid on the list and validates each reading.
        List<@Valid MeterReadingRequest> readings
) {
}
