package ru.omnicio.app.ui.portfolio

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.semantics.*
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import java.math.BigDecimal
import java.math.MathContext
import ru.omnicio.app.ui.terminal.*

/** Calendar gaps remain gaps. Every selected value is an exact persisted observation. */
@Composable
internal fun TerminalValuePlot(points: List<HistoryPoint>, currency: String) {
    val bars = remember(points) { historyBars(points)?.bars.orEmpty() }
    if (bars.isEmpty()) { TerminalChartEmpty("История ещё не накоплена"); return }
    var selected by remember(points) { mutableIntStateOf(bars.indexOfLast { it.close != null }) }
    val amounts = bars.mapNotNull { it.close?.value }
    val min = amounts.minOrNull() ?: BigDecimal.ZERO
    val max = amounts.maxOrNull() ?: BigDecimal.ZERO
    val margin = ((max-min)*BigDecimal("0.1")).max(max.abs()*BigDecimal("0.003")).max(BigDecimal.ONE)
    val low = min-margin
    val high = max+margin
    val span = high-low
    val fractions = bars.map { it.close?.let { p -> (high-p.value).divide(span,MathContext.DECIMAL64).toFloat() } }
    val chosen = bars.getOrNull(selected)?.close
    val grid = MaterialTheme.colorScheme.outlineVariant
    val selectedText = chosen?.let { decimalText(it.value)+" "+currencySymbol(currency)+" · "+dateText(it.date, "dd.MM.yy HH:mm") }
        ?: "На выбранную дату наблюдения нет"
    Text(selectedText, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
    Row(Modifier.fillMaxWidth().height(180.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Column(Modifier.width(58.dp).fillMaxHeight(), verticalArrangement = Arrangement.SpaceBetween) {
            TerminalLabel(compactAxis(high)); TerminalLabel(compactAxis((high+low)/BigDecimal(2))); TerminalLabel(compactAxis(low))
        }
        Canvas(Modifier.weight(1f).fillMaxHeight().semantics {
            contentDescription = "Стоимость портфеля. $selectedText. Разрывы — даты без наблюдений."
            customActions = listOf(
                CustomAccessibilityAction("Предыдущее наблюдение") { selected = (selected-1).coerceAtLeast(0); true },
                CustomAccessibilityAction("Следующее наблюдение") { selected = (selected+1).coerceAtMost(bars.lastIndex); true })
        }.pointerInput(bars.size) {
            detectTapGestures { p -> selected = historyBarIndex(p.x, size.width.toFloat(), bars.size) }
        }.pointerInput(bars.size) {
            detectHorizontalDragGestures { change, _ ->
                change.consume(); selected = historyBarIndex(change.position.x, size.width.toFloat(), bars.size)
            }
        }) {
            for (i in 0..4) {
                val y = size.height*i/4f
                drawLine(grid, Offset(0f,y),Offset(size.width,y),1f)
            }
            val step = size.width/bars.size
            var segment = mutableListOf<Offset>()
            fun render() {
                if (segment.isEmpty()) return
                val path = Path().apply { moveTo(segment.first().x,segment.first().y); segment.drop(1).forEach { lineTo(it.x,it.y) } }
                if (segment.size>1) {
                    val area = Path().apply { addPath(path); lineTo(segment.last().x,size.height); lineTo(segment.first().x,size.height); close() }
                    drawPath(area, Brush.verticalGradient(listOf(TerminalPurple.copy(alpha=.34f),TerminalPurple.copy(alpha=.01f))))
                    drawPath(path,TerminalPurple,style=Stroke(2.dp.toPx()))
                }
                if (segment.size == 1) drawCircle(TerminalPurple,3.dp.toPx(),segment.first())
                segment = mutableListOf()
            }
            fractions.forEachIndexed { index, y ->
                if (y == null) render() else segment.add(Offset((index+.5f)*step,y.coerceIn(0f,1f)*size.height))
            }
            render()
            fractions.getOrNull(selected)?.let { y ->
                val at = Offset((selected+.5f)*step,y*size.height)
                drawLine(TerminalPurple.copy(alpha=.4f),Offset(at.x,0f),Offset(at.x,size.height),1f)
                drawCircle(TerminalLime,4.dp.toPx(),at)
            }
        }
    }
    Row(Modifier.fillMaxWidth().padding(start=66.dp),horizontalArrangement=Arrangement.SpaceBetween) {
        TerminalLabel(bars.first().start.toString().takeLast(5)); TerminalLabel(bars.last().end.toString().takeLast(5))
    }
    TerminalLabel("СТОИМОСТЬ ВКЛЮЧАЕТ ПОПОЛНЕНИЯ")
}

private fun compactAxis(value: BigDecimal): String = when {
    value.abs() >= BigDecimal(1_000_000) -> decimalText(value/BigDecimal(1_000_000),1)+"м"
    value.abs() >= BigDecimal(1_000) -> decimalText(value/BigDecimal(1_000),1)+"к"
    else -> decimalText(value,0)
}

@Composable
internal fun TerminalChartEmpty(message: String) {
    Box(Modifier.fillMaxWidth().heightIn(min=100.dp),contentAlignment=Alignment.Center) {
        Text(message,color=MaterialTheme.colorScheme.onSurfaceVariant,style=MaterialTheme.typography.bodySmall)
    }
}

@Composable
internal fun TerminalDonut(rows: List<TerminalAllocation>, modifier: Modifier = Modifier) {
    val track = MaterialTheme.colorScheme.outlineVariant
    Box(modifier.size(152.dp),contentAlignment=Alignment.Center) {
        Canvas(Modifier.fillMaxSize().semantics {
            contentDescription = rows.joinToString("; ") { it.label+": "+decimalText(it.percent)+"%" }
        }) {
            val width=23.dp.toPx()
            val inset=width/2
            val bounds=Size(size.width-width,size.height-width)
            drawArc(track,0f,360f,false,Offset(inset,inset),bounds,style=Stroke(width))
            var angle=-90f
            rows.forEachIndexed { index,row ->
                val sweep=row.percent.toFloat()*3.6f
                drawArc(TerminalSeries[index%TerminalSeries.size],angle,sweep.coerceAtLeast(0f),false,
                    Offset(inset,inset),bounds,style=Stroke(width))
                angle+=sweep
            }
        }
        Column(horizontalAlignment=Alignment.CenterHorizontally) {
            TerminalLabel("ПОРТФЕЛЬ")
            Text("100%",fontSize=22.sp,fontWeight=FontWeight.SemiBold)
        }
    }
}

@Composable
internal fun TerminalPaymentPlot(rows: List<TerminalPayment>, currency: String) {
    var selected by remember(rows) { mutableIntStateOf(0) }
    val high=rows.maxOfOrNull { it.amount } ?: BigDecimal.ZERO
    val chosen=rows.getOrNull(selected)
    Text(chosen?.let { it.month+" · "+decimalText(it.amount)+" "+currencySymbol(currency) }.orEmpty(),
        style=MaterialTheme.typography.titleSmall,color=TerminalAmber)
    val grid=MaterialTheme.colorScheme.outlineVariant
    Canvas(Modifier.fillMaxWidth().height(132.dp).semantics {
        contentDescription = "Ожидаемые выплаты. "+rows.joinToString("; ") { it.month+": "+it.amount.toPlainString()+" "+currency }
    }.pointerInput(rows.size) { detectTapGestures { p -> selected=historyBarIndex(p.x,size.width.toFloat(),rows.size) } }) {
        for(i in 0..3) drawLine(grid,Offset(0f,size.height*i/3f),Offset(size.width,size.height*i/3f),1f)
        val step=size.width/rows.size
        rows.forEachIndexed { index,row ->
            val fraction=if(high.signum()>0) row.amount.divide(high,MathContext.DECIMAL64).toFloat() else 0f
            val h=(size.height-8.dp.toPx())*fraction
            if(h>0) drawRect(if(index==selected) TerminalAmber else TerminalPurple,
                Offset((index+.25f)*step,size.height-h),Size(step*.5f,h))
        }
    }
    Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {
        TerminalLabel(rows.first().month); TerminalLabel(currencySymbol(currency)); TerminalLabel(rows.last().month)
    }
}
