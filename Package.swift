// swift-tools-version:6.2
import PackageDescription

let package = Package(
    name: "AuroraDrive",
    platforms: [.macOS(.v26)],
    targets: [
        // MetalGoose (GPL v3.0, upstream unmodified) — 仅用于显示路径超分/插帧
        // MGFG-1 插帧需要 macOS 26+ 的 MetalFX；本 target 以 Swift 6 模式编译。
        .target(
            name: "MetalGooseEngine",
            path: "Vendor/MetalGoose/Engine",
            resources: [.copy("Shaders.metal")]
        ),
        .executableTarget(
            name: "AuroraDrive",
            dependencies: ["MetalGooseEngine"],
            path: ".",
            sources: [
                "AuroraDriveApp.swift",
                "AutomationPanel.swift",
                "CaptureEngine.swift",
                "ConfidenceEstimator.swift",
                "ControlEngine.swift",
                "DegradeStateMachine.swift",
                "EscapeController.swift",
                "GameMapView.swift",
                "InferenceEngine.swift",
                "KeyboardMonitor.swift",
                "RecordEngine.swift",
                "RuleController.swift",
                "SpeedOCRReader.swift",
                "YoloEngine.swift"
            ],
            swiftSettings: [
                // 主程序保持 Swift 5 语言模式，避免严格并发模式破坏既有并发代码
                .swiftLanguageMode(.v5)
            ]
        )
    ]
)
