import SwiftUI

@main
struct HomeCamApp: App {
    @StateObject private var vm = CamerasViewModel()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(vm)
                .onAppear { vm.appBecameActive() }
                .onReceive(NotificationCenter.default.publisher(for: UIApplication.willResignActiveNotification)) { _ in
                    vm.appWentInactive()
                }
                .onReceive(NotificationCenter.default.publisher(for: UIApplication.didBecomeActiveNotification)) { _ in
                    vm.appBecameActive()
                }
        }
    }
}
