//! The strip: a 64x2 layer-shell surface, one per output, that the ISS
//! Cockpit shader reads its telemetry out of.
//!
//! This exists because Hyprland binds a fixed, compiled-in set of uniforms to
//! a screen shader (tex, time, wl_output, screen_size, v_texcoord) with no
//! second sampler and no arbitrary-uniform path. `tex` is the composited
//! output, so the only way to hand a screen shader a table of numbers is to
//! put the numbers on the screen. The shader reads them and then paints over
//! them in the same pass, and Hyprland's screencopy runs after the shader, so
//! the strip is invisible both on screen and to `grim`.
//!
//! Everything about this surface is chosen to keep the pixels EXACTLY as
//! written: overlay layer so nothing composites on top, opaque region so
//! nothing blends underneath, no input region so it cannot take a click, and
//! zero exclusive zone so it does not push anybody's windows around. The
//! theme's `hyprland.lua` ships the matching layer rule that turns off blur,
//! dimming, shadow and rounding for this namespace.

use smithay_client_toolkit::compositor::{CompositorHandler, CompositorState, FrameCallbackData};
use smithay_client_toolkit::output::{OutputHandler, OutputState};
use smithay_client_toolkit::registry::{ProvidesRegistryState, RegistryState};
use smithay_client_toolkit::shell::wlr_layer::{
    Anchor, KeyboardInteractivity, Layer, LayerShell, LayerShellHandler, LayerSurface,
    LayerSurfaceConfigure,
};
use smithay_client_toolkit::shell::WaylandSurface;
use smithay_client_toolkit::shm::slot::SlotPool;
use smithay_client_toolkit::shm::{Shm, ShmHandler};
use smithay_client_toolkit::{delegate_registry, registry_handlers};
use wayland_client::globals::registry_queue_init;
use wayland_client::protocol::{wl_output, wl_shm, wl_surface};
use wayland_client::{Connection, QueueHandle};

use crate::gauges::{render, Shared, STRIP_H, STRIP_W};

/// Hyprland matches layer rules on this. It is also what you grep for when
/// you want to know whether the thing is running.
pub const NAMESPACE: &str = "ritzpah-iss-telemetry";

struct Panel {
    layer: LayerSurface,
    output: wl_output::WlOutput,
    configured: bool,
}

struct App {
    registry: RegistryState,
    output_state: OutputState,
    compositor: CompositorState,
    layer_shell: LayerShell,
    shm: Shm,
    pool: SlotPool,
    panels: Vec<Panel>,
    gauges: Shared,
    exit: bool,
}

impl App {
    fn add_output(&mut self, qh: &QueueHandle<Self>, output: wl_output::WlOutput) {
        if self.panels.iter().any(|p| p.output == output) {
            return;
        }
        let surface = self.compositor.create_surface(qh);

        // No input region at all: an empty region means the surface is
        // transparent to the pointer, so it can never eat a click meant for
        // whatever is genuinely at the top-left corner of the screen.
        if let Ok(region) = smithay_client_toolkit::compositor::Region::new(&self.compositor) {
            surface.set_input_region(Some(region.wl_region()));
        }

        let layer = self.layer_shell.create_layer_surface(
            qh,
            surface,
            Layer::Overlay,
            Some(NAMESPACE),
            Some(&output),
        );
        layer.set_size(STRIP_W as u32, STRIP_H as u32);
        layer.set_anchor(Anchor::TOP | Anchor::LEFT);
        layer.set_keyboard_interactivity(KeyboardInteractivity::None);
        // Zero, not -1. -1 would ask to be laid out ignoring other exclusive
        // zones; 0 simply reserves nothing, which is what we want -- the strip
        // must not move anybody's windows.
        layer.set_exclusive_zone(0);
        layer.commit();

        self.panels.push(Panel { layer, output, configured: false });
    }

    fn draw(&mut self, qh: &QueueHandle<Self>) {
        let mut pixels = [0u32; STRIP_W * STRIP_H];
        {
            let g = self.gauges.lock().unwrap_or_else(|e| e.into_inner());
            render(&g, &mut pixels);
        }

        let stride = (STRIP_W * 4) as i32;
        for panel in &self.panels {
            if !panel.configured {
                continue;
            }
            let (buffer, canvas) = match self.pool.create_buffer(
                STRIP_W as i32,
                STRIP_H as i32,
                stride,
                // Xrgb8888, not Argb8888: the alpha channel is the one thing
                // a compositor is entitled to reinterpret, and TELEMETRY.md
                // promises that no value is ever carried in it.
                wl_shm::Format::Xrgb8888,
            ) {
                Ok(v) => v,
                Err(_) => continue,
            };

            for (i, chunk) in canvas.chunks_exact_mut(4).enumerate() {
                chunk.copy_from_slice(&pixels[i].to_le_bytes());
            }

            let surface = panel.layer.wl_surface();

            // Declare the whole surface opaque. Without this a compositor is
            // free to blend whatever is behind the strip into it, and the
            // checksum starts failing for reasons that look like a bug in the
            // daemon.
            if let Ok(region) = smithay_client_toolkit::compositor::Region::new(&self.compositor) {
                region.add(0, 0, STRIP_W as i32, STRIP_H as i32);
                surface.set_opaque_region(Some(region.wl_region()));
            }

            surface.damage_buffer(0, 0, STRIP_W as i32, STRIP_H as i32);
            surface.frame(qh, FrameCallbackData(surface.clone()));
            let _ = buffer.attach_to(surface);
            surface.commit();
        }
    }
}

impl CompositorHandler for App {
    fn scale_factor_changed(
        &mut self,
        _: &Connection,
        _: &QueueHandle<Self>,
        _: &wl_surface::WlSurface,
        _: i32,
    ) {
    }

    fn transform_changed(
        &mut self,
        _: &Connection,
        _: &QueueHandle<Self>,
        _: &wl_surface::WlSurface,
        _: wl_output::Transform,
    ) {
    }

    /// The frame callback is the clock. Repainting in step with the
    /// compositor means the shader never reads a strip that is more than one
    /// frame stale, and costs nothing when the screen is idle.
    fn frame(
        &mut self,
        _: &Connection,
        qh: &QueueHandle<Self>,
        _: &wl_surface::WlSurface,
        _: u32,
    ) {
        self.draw(qh);
    }

    fn surface_enter(
        &mut self,
        _: &Connection,
        _: &QueueHandle<Self>,
        _: &wl_surface::WlSurface,
        _: &wl_output::WlOutput,
    ) {
    }

    fn surface_leave(
        &mut self,
        _: &Connection,
        _: &QueueHandle<Self>,
        _: &wl_surface::WlSurface,
        _: &wl_output::WlOutput,
    ) {
    }
}

impl OutputHandler for App {
    fn output_state(&mut self) -> &mut OutputState {
        &mut self.output_state
    }

    fn new_output(&mut self, _: &Connection, qh: &QueueHandle<Self>, output: wl_output::WlOutput) {
        self.add_output(qh, output);
    }

    fn update_output(&mut self, _: &Connection, _: &QueueHandle<Self>, _: wl_output::WlOutput) {}

    fn output_destroyed(
        &mut self,
        _: &Connection,
        _: &QueueHandle<Self>,
        output: wl_output::WlOutput,
    ) {
        self.panels.retain(|p| p.output != output);
    }
}

impl LayerShellHandler for App {
    fn closed(&mut self, _: &Connection, _: &QueueHandle<Self>, layer: &LayerSurface) {
        self.panels.retain(|p| &p.layer != layer);
        if self.panels.is_empty() {
            self.exit = true;
        }
    }

    fn configure(
        &mut self,
        _: &Connection,
        qh: &QueueHandle<Self>,
        layer: &LayerSurface,
        _: LayerSurfaceConfigure,
        _: u32,
    ) {
        if let Some(panel) = self.panels.iter_mut().find(|p| &p.layer == layer) {
            panel.configured = true;
        }
        self.draw(qh);
    }
}

impl ShmHandler for App {
    fn shm_state(&mut self) -> &mut Shm {
        &mut self.shm
    }
}

impl ProvidesRegistryState for App {
    fn registry(&mut self) -> &mut RegistryState {
        &mut self.registry
    }
    registry_handlers![OutputState];
}

delegate_registry!(App);
// SCTK 0.21 folded the per-protocol delegate_* macros into one blanket macro;
// this covers compositor, output, shm and layer-shell in a single expansion.
smithay_client_toolkit::delegate_dispatch2!(App);

/// Run the Wayland side. Blocks until the compositor goes away, which is the
/// one condition that should take the whole daemon down with it -- without a
/// compositor there is nowhere to put the pixels.
pub fn run(gauges: Shared) -> Result<(), Box<dyn std::error::Error>> {
    let conn = Connection::connect_to_env()?;
    let (globals, mut queue) = registry_queue_init(&conn)?;
    let qh = queue.handle();

    let compositor = CompositorState::bind(&globals, &qh)?;
    let layer_shell = LayerShell::bind(&globals, &qh)?;
    let shm = Shm::bind(&globals, &qh)?;
    let pool = SlotPool::new(STRIP_W * STRIP_H * 4, &shm)?;

    let mut app = App {
        registry: RegistryState::new(&globals),
        output_state: OutputState::new(&globals, &qh),
        compositor,
        layer_shell,
        shm,
        pool,
        panels: Vec::new(),
        gauges,
        exit: false,
    };

    // The first roundtrip is what delivers the outputs that already exist.
    queue.roundtrip(&mut app)?;
    let outputs: Vec<_> = app.output_state.outputs().collect();
    for output in outputs {
        app.add_output(&qh, output);
    }

    while !app.exit {
        queue.blocking_dispatch(&mut app)?;
    }
    Ok(())
}
