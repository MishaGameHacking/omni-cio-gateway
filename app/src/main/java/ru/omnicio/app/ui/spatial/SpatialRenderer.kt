package ru.omnicio.app.ui.spatial

import android.animation.ValueAnimator
import android.content.Context
import android.content.BroadcastReceiver
import android.content.Intent
import android.content.IntentFilter
import android.opengl.Matrix
import android.os.PowerManager
import android.view.Choreographer
import android.view.Surface
import android.view.TextureView
import android.util.Log
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.lerp
import com.google.android.filament.Camera
import com.google.android.filament.Engine
import com.google.android.filament.EntityManager
import com.google.android.filament.IndirectLight
import com.google.android.filament.LightManager
import com.google.android.filament.MaterialInstance
import com.google.android.filament.Renderer
import com.google.android.filament.SwapChain
import com.google.android.filament.View
import com.google.android.filament.Viewport
import com.google.android.filament.android.UiHelper
import com.google.android.filament.gltfio.AssetLoader
import com.google.android.filament.gltfio.FilamentAsset
import com.google.android.filament.gltfio.FilamentInstance
import com.google.android.filament.gltfio.Gltfio
import com.google.android.filament.gltfio.ResourceLoader
import com.google.android.filament.gltfio.UbershaderProvider
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.CancellationException
import org.json.JSONObject
import ru.omnicio.app.ui.spectrum.SpectrumPalette
import java.nio.ByteBuffer
import java.security.MessageDigest
import kotlin.math.PI
import kotlin.math.max
import kotlin.math.min
import kotlin.math.pow
import kotlin.math.sin

/** UI-thread lifetime count across owners, so diagnostics can reveal a leaked Engine. */
internal object SpatialNativeLifetime {
    var engines = 0
        private set
    fun created() { engines++ }
    fun destroyed() { check(engines > 0); engines-- }
}

/** One owner per Activity composition. Every JNI call below runs on its UI thread. */
internal class SpatialOwner(private val context: Context) : Choreographer.FrameCallback {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val choreographer = Choreographer.getInstance()
    private val power = context.getSystemService(PowerManager::class.java)
    private val pools = linkedMapOf<AssetKey, AssetPool>()
    private val loading = mutableSetOf<AssetKey>()
    private val failures = mutableSetOf<AssetKey>()
    private val windows = mutableSetOf<SpatialRenderWindow>()
    private val intervals = ArrayDeque<Double>()
    private val submits = ArrayDeque<Double>()
    private var scheduled = false
    private var lastFrame = 0L
    private var nextId = 0L
    private var closing = false
    private var closed = false
    private var frames = 0L
    internal val submittedFrameCount: Long get() = frames
    private var skipped = 0L
    private var thermal = power?.currentThermalStatus ?: PowerManager.THERMAL_STATUS_NONE
    internal val thermalStatus: Int get() = thermal
    internal val systemMotionEnabled: Boolean get() = ValueAnimator.areAnimatorsEnabled()
    internal val powerSaveMode: Boolean get() = power?.isPowerSaveMode == true
    private val durationScaleListener = ValueAnimator.DurationScaleChangeListener { invalidate() }
    private val thermalListener = PowerManager.OnThermalStatusChangedListener { status ->
        thermal = status; invalidate()
    }
    private val powerReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) { invalidate() }
    }
    var diagnostics by mutableStateOf(SpatialDiagnostics())
        private set
    var motion = SpatialMotion.Live
    var tactile = true
    var opaque = false
    var navigationProgress = 0f
        private set
    var foreground = true
        set(value) {
            field = value
            if (value) invalidate() else {
                choreographer.removeFrameCallback(this);scheduled = false;lastFrame=0
                windows.forEach { it.withdrawFrameRate() }
            }
        }
    private var palette: SpectrumPalette? = null
    val reducedQuality: Boolean get() = thermal >= PowerManager.THERMAL_STATUS_MODERATE || power?.isPowerSaveMode == true
    val effectiveMotion: SpatialMotion get() = when {
        !ValueAnimator.areAnimatorsEnabled() || thermal >= PowerManager.THERMAL_STATUS_SEVERE -> SpatialMotion.Off
        reducedQuality && motion == SpatialMotion.Live -> SpatialMotion.Subdued
        else -> motion
    }

    var engine: Engine? = null
        private set
    private var provider: UbershaderProvider? = null
    private var loader: AssetLoader? = null
    private var resources: ResourceLoader? = null
    private var light = 0
    private var shadowsEnabled = true
    private var ambient: IndirectLight? = null

    init {
        try {
            Gltfio.init()
            Engine.create(Engine.Backend.OPENGL).also { e ->
                engine = e
                SpatialNativeLifetime.created()
                provider = UbershaderProvider(e)
                loader = AssetLoader(e, requireNotNull(provider), EntityManager.get())
                resources = ResourceLoader(e)
                light = EntityManager.get().create()
                LightManager.Builder(LightManager.Type.DIRECTIONAL)
                    .color(1f,.97f,.93f).intensity(95_000f).direction(-.4f,-.65f,-1f)
                    .castShadows(true).shadowOptions(LightManager.ShadowOptions().apply {
                        mapSize=1024;shadowCascades=1;normalBias=.2f;shadowFarHint=1000f
                    }).build(e,light)
                ambient = IndirectLight.Builder().irradiance(1,floatArrayOf(.65f,.69f,.78f))
                    .intensity(24_000f).build(e)
            }
        } catch (failure: LinkageError) {
            Log.e("Spectrum3D","Native renderer initialization failed",failure)
            diagnostics = SpatialDiagnostics(error="Не удалось загрузить графический модуль")
            destroyNative()
        } catch (failure: RuntimeException) {
            Log.e("Spectrum3D","Renderer initialization failed",failure)
            diagnostics = SpatialDiagnostics(error="Графический модуль недоступен на устройстве")
            destroyNative()
        }
        power?.addThermalStatusListener(context.mainExecutor,thermalListener)
        ValueAnimator.registerDurationScaleChangeListener(durationScaleListener)
        context.registerReceiver(powerReceiver, IntentFilter(PowerManager.ACTION_POWER_SAVE_MODE_CHANGED), Context.RECEIVER_NOT_EXPORTED)
    }

    fun id(): Long = ++nextId
    fun updateNavigationProgress(value: Float) {
        val normalized = value.takeIf { it.isFinite() }?.coerceIn(0f, 1f) ?: 0f
        if (navigationProgress != normalized) { navigationProgress = normalized; invalidate() }
    }
    fun configure(colors: SpectrumPalette, mode: SpatialMotion, haptics: Boolean, solid: Boolean) {
        val changed=palette!=colors || motion!=mode || tactile!=haptics || opaque!=solid
        palette=colors;motion=mode;tactile=haptics;opaque=solid
        if (changed) invalidate()
    }
    fun createWindow(): SpatialRenderWindow? = engine?.let {
        SpatialRenderWindow(this,it,light,ambient).also { window -> windows.add(window) }
    }
    fun releaseWindow(window: SpatialRenderWindow) {
        if (windows.remove(window)) window.destroy()
        maybeClose()
        if (!closing) invalidate()
    }
    fun invalidate() {
        if (!foreground || closed || engine==null) return
        windows.forEach { it.dirty = max(it.dirty,3) }
        if (!scheduled) {scheduled=true;choreographer.postFrameCallback(this)}
    }
    fun afterChanged() { invalidate() }

    private data class AssetKey(val asset: SpatialAsset, val low: Boolean)
    internal inner class Lease(val pool: AssetPool, val instance: FilamentInstance, val materials: List<MaterialInstance>) {
        val transform = requireNotNull(engine).transformManager.getInstance(instance.root)
        var taken=false
        fun release() { taken=false }
    }
    private data class MeshSource(val bytes: ByteArray, val material: SpatialMaterial)
    internal inner class AssetPool(val asset: FilamentAsset, val material: SpatialMaterial) {
        val leases=mutableListOf<Lease>()
        var usedFirst=false
        fun acquire(): Lease {
            leases.firstOrNull { !it.taken }?.let { it.taken=true;return it }
            // Keep source data until owner teardown: createInstance explicitly needs it.
            // Instances are bounded by the screen's high-water mark and recycled thereafter.
            val instance=if (!usedFirst) asset.instance.also { usedFirst=true }
                else requireNotNull(loader?.createInstance(asset))
            val cloned=mutableMapOf<MaterialInstance,MaterialInstance>()
            val rm=requireNotNull(engine).renderableManager
            for (entity in instance.entities) {
                val r=rm.getInstance(entity)
                if (r==0) continue
                for (p in 0 until rm.getPrimitiveCount(r)) {
                    val original=rm.getMaterialInstanceAt(r,p)
                    val copy=cloned.getOrPut(original) { MaterialInstance.duplicate(original,"Spectrum instance") }
                    rm.setMaterialInstanceAt(r,p,copy)
                }
            }
            return Lease(this,instance,cloned.values.toList()).also { it.taken=true;leases.add(it) }
        }
    }

    fun acquire(asset: SpatialAsset): Lease? {
        val key=AssetKey(asset,reducedQuality)
        pools[key]?.let { return it.acquire() }
        if (key in loading || key in failures || closed) return null
        loading.add(key)
        scope.launch {
            try {
                val source=withContext(Dispatchers.IO) {
                    when(asset) {
                        is SpatialAsset.Glyph -> MeshSource(SpatialGlyphs.mesh(asset.letter), SpatialMaterial.Ceramic)
                        is SpatialAsset.Wedge -> MeshSource(SpatialGeometry.wedge(asset,key.low), SpatialMaterial.Ceramic)
                        is SpatialAsset.Catalogue -> {
                            require(asset.name.matches(Regex("[a-z_]+")))
                            val name=asset.name+if (key.low) "_low" else ""
                            val catalogue=context.assets.open("spectrum3d/catalogue.json").bufferedReader().use { JSONObject(it.readText()) }
                            require(catalogue.getInt("version")==1)
                            val expected=catalogue.getJSONObject("models").getJSONObject(name)
                            val data=context.assets.open("spectrum3d/$name.glb").use { it.readBytes() }
                            require(data.size==expected.getInt("bytes"))
                            val hash=MessageDigest.getInstance("SHA-256").digest(data).joinToString("") { "%02x".format(it.toInt() and 255) }
                            require(hash==expected.getString("sha256")) { "Catalogue digest mismatch" }
                            MeshSource(data, SpatialMaterial.fromCatalogue(expected.getString("material")))
                        }
                    }
                }
                if (!closed) {
                    val model=requireNotNull(loader?.createAsset(ByteBuffer.wrap(source.bytes)))
                    requireNotNull(resources).loadResources(model)
                    pools[key]=AssetPool(model, source.material)
                    trimWedges()
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (failure: Exception) {
                Log.e("Spectrum3D","Local mesh initialization failed",failure)
                failures.add(key)
                diagnostics=diagnostics.copy(error="Не удалось загрузить объёмное оформление")
            } finally { loading.remove(key);invalidate() }
        }
        return null
    }

    private fun trimWedges() {
        // A new financial allocation replaces an old mesh, without an unbounded geometry cache.
        val stale=pools.filter { (key,pool) -> key.asset is SpatialAsset.Wedge && pool.leases.none { it.taken } }.keys
        stale.toList().dropLast(24).forEach { key -> pools.remove(key)?.let(::destroyPool) }
    }
    private fun destroyPool(pool: AssetPool) {
        pool.leases.forEach { lease -> lease.materials.forEach { engine?.destroyMaterialInstance(it) } }
        loader?.destroyAsset(pool.asset)
    }

    override fun doFrame(frameTimeNanos: Long) {
        scheduled=false
        if (!foreground || closed) return
        val minPeriod=if (reducedQuality || effectiveMotion==SpatialMotion.Subdued) 30_000_000L else 14_000_000L
        if (lastFrame!=0L && frameTimeNanos-lastFrame<minPeriod) {
            scheduled=true;choreographer.postFrameCallback(this);return
        }
        val interval=if(lastFrame==0L) 0.0 else (frameTimeNanos-lastFrame)/1e6
        lastFrame=frameTimeNanos
        val start=System.nanoTime()
        if(shadowsEnabled==reducedQuality){
            engine?.lightManager?.let { it.setShadowCaster(it.getInstance(light),!reducedQuality) }
            shadowsEnabled=!reducedQuality
        }
        var moving=false;var rendered=false
        val colors=palette
        if (colors!=null) windows.forEach { window ->
            if (window.hasSurface) {
                moving=window.update(frameTimeNanos,colors) || moving
                if (window.dirty>0 || moving) {
                    if (window.render(frameTimeNanos)) { frames++;rendered=true } else skipped++
                }
            }
        }
        if (rendered) {
            if (interval > 0.0) {intervals.addLast(interval);if(intervals.size>240)intervals.removeFirst()}
            submits.addLast((System.nanoTime()-start)/1e6);if(submits.size>240)submits.removeFirst()
        }
        val pending=moving || windows.any { it.hasSurface && it.dirty>0 }
        if (pending) {scheduled=true;choreographer.postFrameCallback(this)} else {
            lastFrame=0;windows.forEach { it.withdrawFrameRate() }
        }
        if (!pending || frames%30L==0L) diagnostics=SpatialDiagnostics(
            engineCount=SpatialNativeLifetime.engines,windowCount=windows.count { it.hasSurface },
            submittedFrames=frames,skippedFrames=skipped,
            frameIntervalP95Ms=percentile(intervals),cpuSubmitP95Ms=percentile(submits),
            visibleMeshes=windows.sumOf { it.meshCount },cachedAssets=pools.size,pendingAssets=loading.size,
            pooledInstances=pools.values.sumOf { it.leases.size },
            quality=if(reducedQuality)"economy" else "standard",error=diagnostics.error,
        )
    }
    private fun percentile(values: Collection<Double>): Double = values.sorted().let { if(it.isEmpty())0.0 else it[((it.size-1)*.95).toInt()] }
    fun close() { closing=true;maybeClose() }
    private fun maybeClose() {
        if (!closing || windows.isNotEmpty() || closed) return
        closed=true;scope.cancel();choreographer.removeFrameCallback(this)
        power?.removeThermalStatusListener(thermalListener)
        ValueAnimator.unregisterDurationScaleChangeListener(durationScaleListener)
        context.unregisterReceiver(powerReceiver)
        pools.values.forEach(::destroyPool);pools.clear()
        destroyNative()
    }
    private fun destroyNative() {
        resources?.destroy();loader?.destroy();provider?.destroyMaterials();provider?.destroy()
        ambient?.let { engine?.destroyIndirectLight(it) }
        if(light!=0){engine?.destroyEntity(light);EntityManager.get().destroy(light)}
        engine?.let { it.destroy();SpatialNativeLifetime.destroyed() }
        resources=null;loader=null;provider=null;ambient=null;light=0;engine=null
    }
}

internal class SpatialRenderWindow(
    private val owner: SpatialOwner,private val engine: Engine, light: Int, ambient: IndirectLight?,
) : UiHelper.RendererCallback {
    private val renderer=engine.createRenderer()
        .apply { clearOptions=Renderer.ClearOptions().apply { clear=true;clearColor=doubleArrayOf(0.0,0.0,0.0,0.0) } }
    private val scene=engine.createScene().apply { addEntity(light);indirectLight=ambient }
    private val cameraEntity=EntityManager.get().create()
    private val camera=engine.createCamera(cameraEntity).apply { setExposure(16f,1f/125f,100f) }
    private var msaaSamples=if(owner.reducedQuality)2 else 4
    private val view=engine.createView().apply {
        scene=this@SpatialRenderWindow.scene;camera=this@SpatialRenderWindow.camera
        blendMode=View.BlendMode.TRANSLUCENT
        // Per-material scissor clips meshes to native layout. Dynamic resolution is incompatible.
        // The GLES 3.0 software driver used by the Android 15 ps16k image aborts
        // while linking Filament 1.72.1's translucent FXAA pass. Use geometry MSAA
        // instead; keep post-processing for PBR tone mapping and gamma encoding.
        antiAliasing=View.AntiAliasing.NONE
        setPostProcessingEnabled(true)
        multiSampleAntiAliasingOptions=multisampling(msaaSamples)
    }
    private val ui=UiHelper(UiHelper.ContextErrorPolicy.DONT_CHECK).apply {isOpaque=false;renderCallback=this@SpatialRenderWindow}
    private var swap: SwapChain?=null
    private var surface: Surface?=null
    private var width=0;private var height=0
    private val slots=linkedMapOf<Long,SpatialSlot>()
    private val instances=linkedMapOf<String,ActiveMesh>()
    private var destroyed=false
    private var votedRate=0f
    var density=1f
    var origin=Offset.Zero
    var dirty=3
    var drawnModels by mutableStateOf<Set<String>>(emptySet())
        private set
    var localBackProgress by mutableStateOf(0f)
        private set
    val hasSurface get()=ui.isReadyToRender && swap!=null && !destroyed
    val meshCount get()=instances.size
    private fun multisampling(samples: Int)=View.MultiSampleAntiAliasingOptions().apply {
        enabled=true;sampleCount=samples;customResolve=false
    }
    private data class ActiveMesh(val asset: SpatialAsset,val low: Boolean,val lease: SpatialOwner.Lease,
        var primitive: SpatialPrimitive,var changedAt: Long,var matrix: FloatArray=FloatArray(16),
        var bounds: Rect?=null,var target: Rect?=null,var transferFrom: Rect?=null,var transferStart:Long=0L,
        var sourceSlot:Long=0L,var previousRect:Rect?=null,var normalizedRect:Rect?=null,
        var previousDepth:Float?=null,var currentDepth:Float?=null,
        val appliedMatrix:FloatArray=FloatArray(16),var color:Color?=null,var selected:Boolean=false,
        var opaque:Boolean?=null,var clip:Rect?=null)

    fun attach(texture: TextureView) {texture.isOpaque=false;ui.attachTo(texture)}
    fun updateLocalBackProgress(value: Float) {
        val next = if (owner.effectiveMotion == SpatialMotion.Off) 0f
            else value.takeIf { it.isFinite() }?.coerceIn(0f, 1f) ?: 0f
        if (localBackProgress != next) { localBackProgress = next; owner.invalidate() }
    }
    fun put(slot: SpatialSlot) {if(slots[slot.id]!=slot){slots[slot.id]=slot;owner.afterChanged()}}
    fun remove(id:Long) {if(slots.remove(id)!=null)owner.afterChanged()}

    override fun onNativeWindowChanged(surface: Surface) {
        swap?.let(engine::destroySwapChain)
        votedRate=0f
        this.surface=surface;swap=engine.createSwapChain(surface,ui.swapChainFlags);owner.invalidate()
    }
    override fun onDetachedFromSurface() {
        swap?.let { engine.destroySwapChain(it);engine.flushAndWait() };swap=null;surface=null
        votedRate=0f
    }
    override fun onResized(width:Int,height:Int) {
        this.width=width;this.height=height
        if(width>0&&height>0){
            view.viewport=Viewport(0,0,width,height)
            camera.setProjection(Camera.Projection.ORTHO,0.0,width.toDouble(),0.0,height.toDouble(),1.0,1000.0)
            camera.lookAt(0.0,0.0,500.0,0.0,0.0,0.0,0.0,1.0,0.0)
        }
        owner.invalidate()
    }

    fun update(now:Long,palette:SpectrumPalette):Boolean {
        val samples=if(owner.reducedQuality)2 else 4
        if(msaaSamples!=samples){
            view.multiSampleAntiAliasingOptions=multisampling(samples)
            msaaSamples=samples
        }
        val live=mutableSetOf<String>();var animated=false
        // During shared-element overlap the destination's later slot wins. This
        // preserves a single entity and material instance, not a duplicate model.
        val sharedDestinations=mutableMapOf<String,Long>()
        for(slot in slots.values) for(primitive in slot.primitives) {
            primitive.sharedKey?.let { sharedDestinations[it]=slot.id }
        }
        for(slot in slots.values){
            val bounds=slot.bounds.translate(-origin.x,-origin.y)
            val clipping=slot.clip.translate(-origin.x,-origin.y).intersect(Rect(0f,0f,width.toFloat(),height.toFloat()))
            if(clipping.width<=0f||clipping.height<=0f||bounds.width<=0f||bounds.height<=0f)continue
            slot.primitives.forEachIndexed { index,p ->
                if(p.sharedKey!=null&&sharedDestinations[p.sharedKey]!=slot.id)return@forEachIndexed
                val w=bounds.width*p.rect.width;val h=bounds.height*p.rect.height
                if(w<=0f||h<=0f)return@forEachIndexed
                val id=p.sharedKey?.let { "object/$it" } ?: "${slot.id}/${p.key}/$index";live.add(id)
                var mesh=instances[id]
                if(mesh!=null&&(mesh.asset!=p.asset||mesh.low!=owner.reducedQuality)){
                    val replacement=owner.acquire(p.asset)
                    if(replacement!=null){
                        scene.removeEntities(mesh.lease.instance.entities);mesh.lease.release()
                        mesh=ActiveMesh(p.asset,owner.reducedQuality,replacement,p,now)
                        instances[id]=mesh;scene.addEntities(replacement.instance.entities)
                    }
                }
                if(mesh==null){
                    val lease=owner.acquire(p.asset) ?: return@forEachIndexed
                    mesh=ActiveMesh(p.asset,owner.reducedQuality,lease,p,now)
                    mesh.previousDepth=p.depth-4f
                    instances[id]=mesh;scene.addEntities(lease.instance.entities)
                }
                if(mesh.primitive.state!=p.state||mesh.primitive.rect!=p.rect||mesh.primitive.depth!=p.depth){
                    mesh.changedAt=now;mesh.previousRect=mesh.normalizedRect;mesh.previousDepth=mesh.currentDepth
                }
                mesh.primitive=p
                val motion=if(p.motionAllowed)owner.effectiveMotion else SpatialMotion.Off
                val elapsed=(now-mesh.changedAt)/1e9
                val busy=p.state==SpatialState.Loading&&motion==SpatialMotion.Live
                val duration=if(motion==SpatialMotion.Subdued).16 else .52
                val active=motion!=SpatialMotion.Off&&(elapsed<duration||busy)
                animated=animated||active
                val wave=if(active)sin(min(elapsed/duration,1.0)*PI).toFloat() else 0f
                val progress=if(motion==SpatialMotion.Off)1f else (elapsed/duration).toFloat().coerceIn(0f,1f)
                val eased=progress*progress*(3f-2f*progress)
                val normalized=mesh.previousRect?.let { androidx.compose.ui.geometry.lerp(it,p.rect,eased) } ?: p.rect
                mesh.normalizedRect=normalized
                val depth=mesh.previousDepth?.let { it+(p.depth-it)*eased } ?: p.depth
                mesh.currentDepth=depth
                val target=Rect(bounds.left+bounds.width*normalized.left,bounds.top+bounds.height*normalized.top,
                    bounds.left+bounds.width*normalized.right,bounds.top+bounds.height*normalized.bottom)
                if(mesh.target!=target){
                    if(p.sharedKey!=null&&mesh.sourceSlot!=slot.id){
                        mesh.transferFrom=mesh.bounds;mesh.transferStart=now
                    }
                    mesh.target=target
                }
                mesh.sourceSlot=slot.id
                val transferDuration=if(motion==SpatialMotion.Subdued).12 else .32
                val fraction=if(motion==SpatialMotion.Off||p.sharedKey==null)1f
                    else ((now-mesh.transferStart)/1e9/transferDuration).toFloat().coerceIn(0f,1f)
                val from=mesh.transferFrom
                val positioned=if(from!=null&&fraction<1f) androidx.compose.ui.geometry.lerp(from,target,
                    fraction*fraction*(3f-2f*fraction)) else target
                if(from!=null&&fraction<1f)animated=true
                if(fraction>=1f)mesh.transferFrom=null
                mesh.bounds=positioned
                val x=(positioned.left+positioned.right)/2
                val y=height-(positioned.top+positioned.bottom)/2
                val pressed=if(p.state==SpatialState.Pressed)1f else 0f
                val assetName=(p.asset as? SpatialAsset.Catalogue)?.name
                val scale=1f-pressed*.035f+if(assetName=="goal")wave*.035f else 0f
                Matrix.setIdentityM(mesh.matrix,0)
                val backProgress = if (owner.effectiveMotion == SpatialMotion.Off) 0f
                    else max(owner.navigationProgress, localBackProgress)
                Matrix.translateM(mesh.matrix,0,x,y,(depth-pressed*2f-backProgress*48f)*density)
                if (p.rotationY != 0f) Matrix.rotateM(mesh.matrix, 0, p.rotationY, 0f, 1f, 0f)
                if(p.tilt){
                    val nod=if(assetName=="avatar"||assetName=="analyst"||assetName=="brand")wave*9f else wave*4f
                    Matrix.rotateM(mesh.matrix,0,-7f+nod,1f,0f,0f)
                    Matrix.rotateM(mesh.matrix,0,9f+wave*if(assetName=="globe"||assetName=="orbit")22f else 8f,0f,1f,0f)
                    if(assetName=="notifications")Matrix.rotateM(mesh.matrix,0,
                        (sin(elapsed*28)*wave*11).toFloat(),0f,0f,1f)
                    if(busy)Matrix.rotateM(mesh.matrix,0,(elapsed*50%360).toFloat(),0f,1f,0f)
                }
                Matrix.scaleM(mesh.matrix,0,positioned.width*scale,positioned.height*scale,p.thickness*density)
                if(!mesh.matrix.contentEquals(mesh.appliedMatrix)){
                    engine.transformManager.setTransform(mesh.lease.transform,mesh.matrix)
                    mesh.matrix.copyInto(mesh.appliedMatrix)
                }
                val color=if(p.state==SpatialState.Disabled)lerp(p.color,palette.card,.5f) else p.color
                val brightness=if(p.state==SpatialState.Selected)1.08f else 1f
                val selected=p.state==SpatialState.Selected
                if(mesh.color!=color||mesh.selected!=selected){
                    val r=linear(color.red)*brightness;val g=linear(color.green)*brightness;val b=linear(color.blue)*brightness
                    mesh.lease.materials.forEach { it.setParameter("baseColorFactor",r,g,b,1f) }
                    mesh.color=color;mesh.selected=selected
                }
                if(mesh.opaque!=owner.opaque){
                    val preset = mesh.lease.pool.material
                    val appearance = preset.appearance(owner.opaque)
                    mesh.lease.materials.forEach {
                        it.setParameter("roughnessFactor", appearance.roughness)
                        it.setParameter("metallicFactor", appearance.metallic)
                        if (preset.clearCoat > 0f) {
                            // Filament 1.72.1 gltfio AssetLoader parameter spelling.
                            it.setParameter("clearCoatFactor", appearance.clearCoat)
                            it.setParameter("clearCoatRoughnessFactor", preset.clearCoatRoughness)
                        }
                    }
                    mesh.opaque=owner.opaque
                }
                val clip=if(from!=null&&fraction<1f)Rect(0f,0f,width.toFloat(),height.toFloat()) else clipping
                if(mesh.clip!=clip){
                    mesh.lease.materials.forEach { it.setScissor(clip.left.toInt().coerceAtLeast(0),
                        (height-clip.bottom).toInt().coerceAtLeast(0),clip.width.toInt(),clip.height.toInt()) }
                    mesh.clip=clip
                }
            }
        }
        val stale=instances.keys.filter { it !in live }
        stale.forEach { key -> instances.remove(key)?.let { scene.removeEntities(it.lease.instance.entities);it.lease.release() } }
        if(animated)dirty=max(dirty,2)
        return animated
    }
    private fun linear(c:Float)=if(c<=.04045f)c/12.92f else ((c+.055f)/1.055f).pow(2.4f)

    fun render(time:Long):Boolean {
        val chain=swap?:return false
        if(!renderer.beginFrame(chain,time))return false
        renderer.render(view);renderer.endFrame();dirty=(dirty-1).coerceAtLeast(0)
        val drawn=instances.values.mapNotNull { (it.asset as? SpatialAsset.Catalogue)?.name }.toSet()
        if(!drawnModels.containsAll(drawn))drawnModels=drawnModels+drawn
        val rate=if(owner.reducedQuality || owner.effectiveMotion==SpatialMotion.Subdued)30f else 60f
        if(votedRate!=rate){
            surface?.takeIf { it.isValid }?.setFrameRate(rate,Surface.FRAME_RATE_COMPATIBILITY_DEFAULT,Surface.CHANGE_FRAME_RATE_ONLY_IF_SEAMLESS)
            votedRate=rate
        }
        return true
    }
    fun withdrawFrameRate(){
        if(votedRate!=0f)surface?.takeIf { it.isValid }?.setFrameRate(0f,Surface.FRAME_RATE_COMPATIBILITY_DEFAULT,Surface.CHANGE_FRAME_RATE_ONLY_IF_SEAMLESS)
        votedRate=0f
    }
    fun destroy(){
        if(destroyed)return
        withdrawFrameRate();ui.detach();destroyed=true
        instances.values.forEach { scene.removeEntities(it.lease.instance.entities);it.lease.release() };instances.clear();slots.clear()
        engine.destroyView(view);engine.destroyRenderer(renderer);engine.destroyScene(scene)
        engine.destroyCameraComponent(cameraEntity);EntityManager.get().destroy(cameraEntity)
    }
}
