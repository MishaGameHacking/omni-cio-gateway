package ru.omnicio.app.ui.spatial

/** Versioned catalogue material names; shared by loading, native PBR and dynamic meshes. */
internal enum class SpatialMaterial(
    val catalogueName: String,
    val metallic: Float,
    val roughness: Float,
    val clearCoat: Float = 0f,
    val clearCoatRoughness: Float = 0f,
) {
    Ceramic("ceramic", .04f, .46f),
    Metal("metal", .72f, .28f),
    // Opaque dielectric coating with a real extra specular lobe; no refraction claim.
    GlassCoating("glass_coating", 0f, .30f, 1f, .12f);

    data class Appearance(val metallic: Float, val roughness: Float, val clearCoat: Float)

    fun appearance(opaque: Boolean): Appearance = if (opaque)
        Appearance(metallic.coerceAtMost(.12f), roughness.coerceAtLeast(.64f), 0f)
    else Appearance(metallic, roughness, clearCoat)

    companion object {
        fun fromCatalogue(value: String): SpatialMaterial = entries.firstOrNull { it.catalogueName == value }
            ?: error("Unknown mesh material family")
    }
}
