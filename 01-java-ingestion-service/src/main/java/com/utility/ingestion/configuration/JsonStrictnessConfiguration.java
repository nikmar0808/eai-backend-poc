package com.utility.ingestion.configuration;

import com.fasterxml.jackson.databind.cfg.CoercionAction;
import com.fasterxml.jackson.databind.cfg.CoercionInputShape;
import com.fasterxml.jackson.databind.type.LogicalType;
import org.springframework.boot.autoconfigure.jackson.Jackson2ObjectMapperBuilderCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Strict JSON types (finding D48). Jackson's default turns a JSON boolean or number into a String ("false", "1234567")
 * and a JSON string into a number ("12.5" -> 12.5). The contract says string and number, and Python refuses a boolean
 * or number for a string field, so the gateway must refuse them too. The refusal is a JsonMappingException with the
 * field's path, which ApiExceptionHandler answers with 400 naming the field.
 */
@Configuration
public class JsonStrictnessConfiguration {

    @Bean
    public Jackson2ObjectMapperBuilderCustomizer strictScalarTypes() {
        // postConfigurer runs on the ObjectMapper that Spring Boot builds, so every other Boot setting is kept.
        return builder -> builder.postConfigurer(mapper -> {
            mapper.coercionConfigFor(LogicalType.Textual)                // target: a String field
                    .setCoercion(CoercionInputShape.Boolean, CoercionAction.Fail)
                    .setCoercion(CoercionInputShape.Integer, CoercionAction.Fail)
                    .setCoercion(CoercionInputShape.Float, CoercionAction.Fail);
            mapper.coercionConfigFor(LogicalType.Float)                  // target: a Double field
                    .setCoercion(CoercionInputShape.String, CoercionAction.Fail);
        });
    }
}