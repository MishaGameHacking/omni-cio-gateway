package ru.omnicio.app.ui.spectrum

import androidx.compose.material3.DatePickerColors
import androidx.compose.material3.DatePickerDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.runtime.Composable

/** Native date selection keeps its behavior while every visible state uses the shared roles. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun spectrumDatePickerColors(): DatePickerColors {
    val c = MaterialTheme.colorScheme
    val s = LocalSpectrumPalette.current.semantic
    return DatePickerDefaults.colors(
        containerColor = c.surface,
        titleContentColor = c.onSurfaceVariant, headlineContentColor = c.onSurface,
        weekdayContentColor = c.onSurfaceVariant, subheadContentColor = c.onSurface,
        navigationContentColor = c.onSurfaceVariant,
        yearContentColor = c.onSurface, disabledYearContentColor = s.disabledInk,
        currentYearContentColor = c.primary,
        selectedYearContentColor = c.onPrimary, selectedYearContainerColor = c.primary,
        disabledSelectedYearContentColor = s.disabledInk, disabledSelectedYearContainerColor = s.disabledContainer,
        dayContentColor = c.onSurface, disabledDayContentColor = s.disabledInk,
        selectedDayContentColor = c.onPrimary, selectedDayContainerColor = c.primary,
        disabledSelectedDayContentColor = s.disabledInk, disabledSelectedDayContainerColor = s.disabledContainer,
        todayContentColor = c.primary, todayDateBorderColor = c.primary,
        dayInSelectionRangeContentColor = c.onPrimaryContainer,
        dayInSelectionRangeContainerColor = c.primaryContainer,
        dividerColor = c.outlineVariant,
        dateTextFieldColors = OutlinedTextFieldDefaults.colors(
            focusedTextColor = c.onSurface, unfocusedTextColor = c.onSurface,
            disabledTextColor = s.disabledInk, errorTextColor = c.onErrorContainer,
            focusedContainerColor = c.surface, unfocusedContainerColor = c.surface,
            disabledContainerColor = s.disabledContainer, errorContainerColor = c.errorContainer,
            cursorColor = c.primary, errorCursorColor = c.error,
            focusedBorderColor = c.primary, unfocusedBorderColor = c.outline,
            disabledBorderColor = c.outlineVariant, errorBorderColor = c.error,
            focusedLabelColor = c.primary, unfocusedLabelColor = c.onSurfaceVariant,
            disabledLabelColor = s.disabledInk, errorLabelColor = c.error,
            focusedPlaceholderColor = c.onSurfaceVariant, unfocusedPlaceholderColor = c.onSurfaceVariant,
            disabledPlaceholderColor = s.disabledInk, errorPlaceholderColor = c.onErrorContainer,
            disabledLeadingIconColor = s.disabledInk, disabledTrailingIconColor = s.disabledInk,
            disabledSupportingTextColor = s.disabledInk, disabledPrefixColor = s.disabledInk,
            disabledSuffixColor = s.disabledInk,
        ),
    )
}
