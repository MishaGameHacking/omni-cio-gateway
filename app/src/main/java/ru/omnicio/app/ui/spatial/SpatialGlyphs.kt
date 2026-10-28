package ru.omnicio.app.ui.spatial

/** First-party geometric alphabet, not a downloaded corporate mark or raster font. */
internal object SpatialGlyphs {
    private val latin = mapOf(
        'A' to "0e11111f111111", 'B' to "1e11111e11111e", 'C' to "0f10101010100f",
        'D' to "1e11111111111e", 'E' to "1f10101e10101f", 'F' to "1f10101e101010",
        'G' to "0f10101711110f", 'H' to "1111111f111111", 'I' to "1f04040404041f",
        'J' to "0702020212120c", 'K' to "11121418141211", 'L' to "1010101010101f",
        'M' to "111b1511111111", 'N' to "11191513111111", 'O' to "0e11111111110e",
        'P' to "1e11111e101010", 'Q' to "0e11111115120d", 'R' to "1e11111e141211",
        'S' to "0f10100e01011e", 'T' to "1f040404040404", 'U' to "1111111111110e",
        'V' to "11111111110a04", 'W' to "11111115151b11", 'X' to "11110a040a1111",
        'Y' to "11110a04040404", 'Z' to "1f01020408101f",
        '0' to "0e11131519110e", '1' to "040c040404040e", '2' to "0e11010204081f",
        '3' to "1e01010601011e", '4' to "02060a121f0202", '5' to "1f10101e01011e",
        '6' to "0e10101e11110e", '7' to "1f010204080808", '8' to "0e11110e11110e",
        '9' to "0e11110f01010e",
    )
    private val cyrillic = mapOf(
        'Б' to "1f10101e11111e", 'Г' to "1f101010101010", 'Д' to "0e0a0a0a0a1f11",
        'Ё' to "0a001f101e101f", 'Ж' to "15150e040e1515", 'З' to "0e11010601110e",
        'И' to "11111315191111", 'Й' to "0a041113151911", 'Л' to "07091111111111",
        'П' to "1f111111111111", 'У' to "11110a04040810", 'Ф' to "041f151f040404",
        'Ц' to "12121212121f01", 'Ч' to "1111110f010101", 'Ш' to "1515151515151f",
        'Щ' to "15151515151f01", 'Ъ' to "1818181e19191e", 'Ы' to "11111119151519",
        'Ь' to "1010101e11111e", 'Э' to "0e11010701110e", 'Ю' to "1215151d151512",
        'Я' to "0f11110f050911",
    )
    private val aliases = mapOf('А' to 'A', 'В' to 'B', 'Е' to 'E', 'К' to 'K', 'М' to 'M',
        'Н' to 'H', 'О' to 'O', 'Р' to 'P', 'С' to 'C', 'Т' to 'T', 'Х' to 'X')

    fun supported(letter: Char): Boolean = letter in latin || letter in cyrillic || letter in aliases

    fun mesh(letter: Char): ByteArray {
        val code = cyrillic[letter] ?: latin[aliases[letter] ?: letter] ?: latin.getValue('I')
        val positions = mutableListOf<Float>()
        val normals = mutableListOf<Float>()
        fun box(left: Float, top: Float, right: Float, bottom: Float) {
            val vertices = arrayOf(floatArrayOf(left,bottom,-.12f),floatArrayOf(right,bottom,-.12f),
                floatArrayOf(right,top,-.12f),floatArrayOf(left,top,-.12f),
                floatArrayOf(left,bottom,.12f),floatArrayOf(right,bottom,.12f),
                floatArrayOf(right,top,.12f),floatArrayOf(left,top,.12f))
            val faces = arrayOf(intArrayOf(4,5,6,7),intArrayOf(1,0,3,2),intArrayOf(0,4,7,3),
                intArrayOf(5,1,2,6),intArrayOf(7,6,2,3),intArrayOf(0,1,5,4))
            val axes = arrayOf(floatArrayOf(0f,0f,1f),floatArrayOf(0f,0f,-1f),floatArrayOf(-1f,0f,0f),
                floatArrayOf(1f,0f,0f),floatArrayOf(0f,1f,0f),floatArrayOf(0f,-1f,0f))
            faces.forEachIndexed { index, face ->
                for (corner in intArrayOf(0,1,2,0,2,3)) {
                    positions.addAll(vertices[face[corner]].toList());normals.addAll(axes[index].toList())
                }
            }
        }
        // Merge adjacent cells within each row into a solid extruded stroke.
        code.chunked(2).map { it.toInt(16) }.forEachIndexed { row, mask ->
            var column = 0
            while (column < 5) {
                if ((mask and (1 shl (4-column))) == 0) { column++;continue }
                val first = column
                while (column < 5 && (mask and (1 shl (4-column))) != 0) column++
                box((first-2.5f)*.14f,(3.5f-row)*.11f,(column-2.5f)*.14f,(2.5f-row)*.11f)
            }
        }
        return SpatialGeometry.glb(positions,normals)
    }
}
