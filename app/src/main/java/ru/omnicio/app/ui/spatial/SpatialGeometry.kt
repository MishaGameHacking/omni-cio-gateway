package ru.omnicio.app.ui.spatial

import org.json.JSONArray
import org.json.JSONObject
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.PI
import kotlin.math.ceil
import kotlin.math.cos
import kotlin.math.max
import kotlin.math.sin
import kotlin.math.sqrt

/** A numeric allocation becomes actual extruded geometry, with front/back/side normals. */
internal object SpatialGeometry {
    fun wedge(asset: SpatialAsset.Wedge, lowDetail: Boolean): ByteArray {
        val steps = max(2, ceil(asset.sweep * if (lowDetail) 36 else 80).toInt())
        val positions = mutableListOf<Float>()
        val normals = mutableListOf<Float>()
        fun point(angle: Double, radius: Double, z: Float) = floatArrayOf(
            (.48 * radius * sin(angle)).toFloat(), (.48 * radius * cos(angle)).toFloat(), z,
        )
        fun triangle(a: FloatArray, b: FloatArray, c: FloatArray) {
            val u = FloatArray(3) { b[it] - a[it] }
            val v = FloatArray(3) { c[it] - a[it] }
            val n = floatArrayOf(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
            val length = sqrt(n.sumOf { (it*it).toDouble() }).toFloat()
            if (length <= 0f) return
            for (p in arrayOf(a,b,c)) { positions.addAll(p.toList()); normals.addAll(n.map { it / length }) }
        }
        fun quad(a: FloatArray,b: FloatArray,c: FloatArray,d: FloatArray) { triangle(a,b,c);triangle(a,c,d) }
        for (i in 0 until steps) {
            val a = (asset.start + asset.sweep * i / steps) * PI * 2
            val b = (asset.start + asset.sweep * (i+1) / steps) * PI * 2
            val ia = point(a,asset.hollow,.1f); val ib=point(b,asset.hollow,.1f)
            val oa = point(a,1.0,.1f); val ob=point(b,1.0,.1f)
            val ial=point(a,asset.hollow,-.1f);val ibl=point(b,asset.hollow,-.1f)
            val oal=point(a,1.0,-.1f);val obl=point(b,1.0,-.1f)
            quad(ia,ib,ob,oa);quad(ial,oal,obl,ibl)
            quad(oa,ob,obl,oal);quad(ib,ia,ial,ibl)
            if (i==0) quad(ia,oa,oal,ial)
            if (i==steps-1) quad(ob,ib,ibl,obl)
        }
        return glb(positions,normals)
    }

    internal fun glb(positions: List<Float>, normals: List<Float>): ByteArray {
        val bytes = ByteBuffer.allocate(positions.size*8).order(ByteOrder.LITTLE_ENDIAN)
        positions.forEach { bytes.putFloat(it) };normals.forEach { bytes.putFloat(it) }
        val posBytes=positions.size*4
        fun array(values: Iterable<*>)=JSONArray().apply { values.forEach { put(it) } }
        val mins=(0..2).map { axis -> positions.filterIndexed { i,_ -> i%3==axis }.minOrNull() ?: 0f }
        val maxs=(0..2).map { axis -> positions.filterIndexed { i,_ -> i%3==axis }.maxOrNull() ?: 0f }
        val document=JSONObject().apply {
            put("asset",JSONObject().put("version","2.0").put("generator","Analyst AI numeric mesh geometry v1"))
            put("scene",0);put("scenes",array(listOf(JSONObject().put("nodes",array(listOf(0))))))
            put("nodes",array(listOf(JSONObject().put("mesh",0))))
            put("meshes",array(listOf(JSONObject().put("primitives",array(listOf(JSONObject()
                .put("attributes",JSONObject().put("POSITION",0).put("NORMAL",1)).put("material",0)))))))
            put("materials",array(listOf(JSONObject().put("pbrMetallicRoughness",JSONObject()
                .put("baseColorFactor",array(listOf(1,1,1,1))).put("metallicFactor",.12).put("roughnessFactor",.4)))))
            put("buffers",array(listOf(JSONObject().put("byteLength",bytes.capacity()))))
            put("bufferViews",array(listOf(JSONObject().put("buffer",0).put("byteOffset",0).put("byteLength",posBytes),
                JSONObject().put("buffer",0).put("byteOffset",posBytes).put("byteLength",posBytes))))
            put("accessors",array(listOf(JSONObject().put("bufferView",0).put("componentType",5126)
                .put("count",positions.size/3).put("type","VEC3").put("min",array(mins)).put("max",array(maxs)),
                JSONObject().put("bufferView",1).put("componentType",5126).put("count",normals.size/3).put("type","VEC3"))))
        }
        val json=document.toString().toByteArray(Charsets.UTF_8)
        val padded=(json.size+3)/4*4
        return ByteBuffer.allocate(12+8+padded+8+bytes.capacity()).order(ByteOrder.LITTLE_ENDIAN).apply {
            putInt(0x46546c67);putInt(2);putInt(capacity());putInt(padded);putInt(0x4e4f534a)
            put(json);repeat(padded-json.size){put(32.toByte())}
            putInt(bytes.capacity());putInt(0x004e4942);put(bytes.array())
        }.array()
    }
}
