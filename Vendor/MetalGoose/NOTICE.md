# MetalGoose — vendored source (GPL v3.0)

This directory contains the **unmodified** source of
[MetalGoose](https://github.com/Stallion77RepoOfficial/MetalGoose),
vendored into AuroraDrive for use as the display-path upscaler / frame
interpolator.

- **Upstream license:** GNU GPL v3.0 — see `LICENSE` in this folder (verbatim
  copy of the upstream LICENSE).
- **Copyright:** the respective MetalGoose authors (see upstream repository).
- **Files here:** `GooseEngine.swift`, `Shaders.metal`, `CaptureSettings.swift`,
  `WindowCaptureManager.swift`, plus the upstream `LICENSE` and `README.md`.
  These are consumed by the `MetalGooseEngine` SwiftPM target and used ONLY to
  upscale / interpolate the on-screen preview in `UpscaleFrameHostView`.

## Modifications

One documented, minimal extension (not a behavioral patch) is applied to
`GooseEngine.swift` so AuroraDrive can feed its **own** already-captured frames
into the engine's display path without starting a second ScreenCaptureKit stream:

- Added a `public func ingest(cgImage:timestamp:)` method that converts a
  `CGImage` → `CVPixelBuffer` (BGRA, with IOSurface) → calls the existing private
  `processSurface(...)`. Everything else in the file is unchanged.

All other vendored files are byte-for-byte upstream. Per GPL v3.0 §5, this file
retains its upstream GPL v3.0 notice and this modification is recorded here.
