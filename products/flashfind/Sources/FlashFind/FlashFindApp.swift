import SwiftUI
import AppKit

@main
struct FlashFindApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var model = SearchViewModel()

    var body: some Scene {
        WindowGroup("FlashFind") {
            ContentView()
                .environmentObject(model)
        }
        .defaultSize(width: 880, height: 560)
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }
}
