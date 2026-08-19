// SPDX-FileCopyrightText: 2026 DuoduoChubbyKitty
// SPDX-License-Identifier: GPL-3.0-or-later
//
// GooseUpscaler — public integration façade for AuroraDrive.
//
// The upstream-vendored `GooseEngine` (GooseEngine.swift) is kept byte-for-byte
// with its members declared `internal` (its original module-internal API).
// This thin, documented wrapper lives in the same `MetalGooseEngine` module and
// re-exposes the minimal surface AuroraDrive needs — `make` / `attachToView` /
// `detachFromView` / `ingest` — as `public`, without patching the vendored source.
//
// Architecture note: frames fed here travel ONLY on the display / overlay path.
// The capture → CoreML inference → key-injection decision chain is never touched
// by this engine (see project NOTICE for the latency-red-line rationale).

import Foundation
import MetalKit

public final class GooseUpscaler {
    private let engine: GooseEngine

    private init(engine: GooseEngine) {
        self.engine = engine
    }

    /// Create a GooseEngine instance (forwards to the internal factory).
    public static func make() -> GooseUpscaler? {
        guard let e = GooseEngine.make() else { return nil }
        return GooseUpscaler(engine: e)
    }

    /// Bind the engine to a host MTKView for on-screen super-res / frame-gen.
    public func attachToView(_ view: MTKView, displayRefreshRate: Int = 60, minRefreshRate: Int = 30) {
        engine.attachToView(view, displayRefreshRate: displayRefreshRate, minRefreshRate: minRefreshRate)
    }

    /// Detach from the MTKView and release GPU resources.
    public func detachFromView() {
        engine.detachFromView()
    }

    /// Push one captured frame (CGImage) into the engine for processing.
    public func ingest(cgImage: CGImage, timestamp: CFTimeInterval = CACurrentMediaTime()) {
        engine.ingest(cgImage: cgImage, timestamp: timestamp)
    }
}
