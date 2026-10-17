package ru.omnicio.app.ui.spatial

import org.junit.Assert.*
import org.junit.Test

class SpatialMaterialTest {
    @Test fun opaquePreferenceRemovesCoatingAndReducesSpecularMetalWithoutLosingMesh() {
        for (material in SpatialMaterial.entries) {
            val normal = material.appearance(false)
            val matte = material.appearance(true)
            assertTrue(matte.roughness >= .64f && matte.roughness >= normal.roughness)
            assertTrue(matte.metallic <= .12f && matte.metallic <= normal.metallic)
            assertEquals(0f, matte.clearCoat, 0f)
            assertEquals(normal, material.appearance(false))
        }
        assertTrue(SpatialMaterial.Metal.metallic > .5f)
        assertTrue(SpatialMaterial.Ceramic.metallic < .1f)
        assertTrue(SpatialMaterial.GlassCoating.clearCoat > .9f)
    }

    @Test fun unknownCatalogueMaterialFailsInsteadOfSilentlyChangingArtwork() {
        for (material in SpatialMaterial.entries) {
            assertEquals(material, SpatialMaterial.fromCatalogue(material.catalogueName))
        }
        try {
            SpatialMaterial.fromCatalogue("unknown")
            fail("Unknown family must fail catalogue loading")
        } catch (_: IllegalStateException) { }
    }
}
