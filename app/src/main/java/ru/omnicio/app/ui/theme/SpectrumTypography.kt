package ru.omnicio.app.ui.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private fun spectrumText(size: Int, height: Int, weight: FontWeight = FontWeight.Normal) = TextStyle(
    fontFamily = FontFamily.SansSerif, fontWeight = weight, fontSize = size.sp, lineHeight = height.sp,
)
internal val SpectrumTypography = Typography(
    displayLarge = spectrumText(40, 46, FontWeight.Bold),
    displayMedium = spectrumText(36, 42, FontWeight.Bold),
    displaySmall = spectrumText(32, 38, FontWeight.Bold),
    headlineLarge = spectrumText(28, 34, FontWeight.Bold),
    headlineMedium = spectrumText(25, 31, FontWeight.Bold),
    headlineSmall = spectrumText(23, 29, FontWeight.SemiBold),
    titleLarge = spectrumText(20, 26, FontWeight.SemiBold),
    titleMedium = spectrumText(17, 23, FontWeight.SemiBold),
    titleSmall = spectrumText(16, 22, FontWeight.Medium),
    bodyLarge = spectrumText(16, 24), bodyMedium = spectrumText(16, 23), bodySmall = spectrumText(14, 20),
    labelLarge = spectrumText(16, 22, FontWeight.SemiBold),
    labelMedium = spectrumText(12, 17, FontWeight.Medium), labelSmall = spectrumText(11, 15, FontWeight.Medium),
)
internal val SpectrumShapes = Shapes(
    extraSmall = RoundedCornerShape(6.dp), small = RoundedCornerShape(10.dp),
    medium = RoundedCornerShape(14.dp), large = RoundedCornerShape(20.dp), extraLarge = RoundedCornerShape(24.dp),
)
