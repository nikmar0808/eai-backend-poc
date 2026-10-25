package com.utility.ingestion.api.dto;

import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.core.JsonToken;
import com.fasterxml.jackson.databind.DeserializationContext;
import com.fasterxml.jackson.databind.deser.std.StdDeserializer;

import java.io.IOException;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.regex.Pattern;

/**
 * Reads a timestamp only from a JSON string that matches the contract's rule (docs/api/README.md):
 * RFC 3339, an offset is mandatory, the offset lies within -14:00 and +14:00, at most six fractional digits.
 * Jackson's default parser accepted a number as seconds since 1970 (finding D29) and offsets up to +-18:00 (D37).
 * The parsed value is converted to UTC, as Spring Boot's default did, so the gateway forwards the same text as before.
 */
public class StrictOffsetDateTimeDeserializer extends StdDeserializer<OffsetDateTime> {

    /** The same expression is in gateway.openapi.yaml and in Python's meter.py: one rule, three places. */
    static final Pattern RFC_3339_WITH_REAL_OFFSET = Pattern.compile(
            "\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(\\.\\d{1,6})?(Z|[+-](0\\d|1[0-3]):[0-5]\\d|[+-]14:00)");

    public StrictOffsetDateTimeDeserializer() {
        super(OffsetDateTime.class);
    }

    @Override
    public OffsetDateTime deserialize(JsonParser parser, DeserializationContext context) throws IOException {
        if (!parser.hasToken(JsonToken.VALUE_STRING)) {
            // A number, a boolean, an object...: a MismatchedInputException, which Spring reports as
            // HttpMessageNotReadableException and ApiExceptionHandler answers with 400 naming the field.
            // Thrown explicitly (not "return context.handleUnexpectedToken(...)") so that JaCoCo counts the line.
            throw context.wrongTokenException(parser, OffsetDateTime.class, JsonToken.VALUE_STRING,
                    "expected an RFC 3339 date-time string");
        }
        String text = parser.getText();
        if (!RFC_3339_WITH_REAL_OFFSET.matcher(text).matches()) {
            throw context.weirdStringException(text, OffsetDateTime.class,
                    "expected an RFC 3339 date-time with an offset between -14:00 and +14:00");
        }
        return OffsetDateTime.parse(text).withOffsetSameInstant(ZoneOffset.UTC);
    }
}