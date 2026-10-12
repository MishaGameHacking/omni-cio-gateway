package ru.omnicio.app.ui.auth

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun TelegramLoginScreen(
    loading: Boolean,
    errorMessage: String?,
    onLoginClick: () -> Unit,
    modifier: Modifier = Modifier,
) {

    Scaffold(
        modifier = modifier.fillMaxSize(),
        containerColor = MaterialTheme.colorScheme.background,
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(horizontal = 22.dp, vertical = 28.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                text = "Analyst AI",
                fontSize = 38.sp,
                lineHeight = 44.sp,
                fontWeight = FontWeight.Bold,
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = "Один аккаунт для портфеля и аналитики",
                style = MaterialTheme.typography.bodyLarge,
                color = Color(0xFF7E858E),
            )
            Spacer(modifier = Modifier.height(28.dp))

            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(30.dp),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            ) {
                Column(
                    modifier = Modifier.padding(
                        PaddingValues(
                            horizontal = 22.dp,
                            vertical = 24.dp,
                        ),
                    ),
                    verticalArrangement = Arrangement.spacedBy(14.dp),
                ) {
                    Text(
                        text = "Вход через Telegram",
                        fontSize = 24.sp,
                        lineHeight = 30.sp,
                        fontWeight = FontWeight.Bold,
                    )
                    Text(
                        text = "Telegram подтверждает ваш уникальный Telegram ID. Пароли Telegram Analyst AI не получает.",
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        style = MaterialTheme.typography.bodyMedium,
                    )

                    errorMessage?.let { message ->
                        Text(
                            text = message,
                            color = Color(0xFFB42318),
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }

                    Button(
                        modifier = Modifier.fillMaxWidth(),
                        enabled = !loading,
                        colors = ButtonDefaults.buttonColors(
                            containerColor = Color(0xFF229ED9),
                            contentColor = Color.White,
                        ),
                        onClick = onLoginClick,
                    ) {
                        if (loading) {
                            CircularProgressIndicator(
                                color = Color.White,
                                strokeWidth = 2.dp,
                            )
                        } else {
                            Text(
                                text = "Войти через Telegram",
                                fontWeight = FontWeight.Bold,
                            )
                        }
                    }
                }
            }
        }
    }
}
