import SwiftUI

struct ContentView: View {
    @EnvironmentObject var vm: CamerasViewModel
    @State private var showSettings = false

    var body: some View {
        NavigationStack {
            Group {
                if vm.serverURL == nil || vm.serverURLString.isEmpty {
                    SettingsView()
                } else {
                    CameraGridView()
                }
            }
            .navigationTitle("HomeCam")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        showSettings = true
                    } label: {
                        Image(systemName: "gearshape")
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        Task { await vm.loadCameras() }
                    } label: {
                        Image(systemName: "arrow.clockwise")
                    }
                    .disabled(vm.isLoading || vm.serverURL == nil)
                }
            }
            .sheet(isPresented: $showSettings) {
                NavigationStack {
                    SettingsView()
                        .toolbar {
                            ToolbarItem(placement: .cancellationAction) {
                                Button("Close") { showSettings = false }
                            }
                        }
                }
            }
            .task {
                // Auto-load once we have a valid server URL
                if vm.serverURL != nil && vm.cameras.isEmpty {
                    await vm.loadCameras()
                }
            }
            .sheet(item: $vm.selectedCamera) { cam in
                CameraDetailView(camera: cam) {
                    vm.deselectCamera()
                }
            }
        }
    }
}

