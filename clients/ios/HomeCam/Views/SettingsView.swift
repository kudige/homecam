import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var vm: CamerasViewModel
    @State private var urlText: String = ""

    var body: some View {
        Form {
            Section("Server") {
                TextField("https://example.com:17017", text: $urlText)
                    .textInputAutocapitalization(.never)
                    .keyboardType(.URL)
                    .autocorrectionDisabled()
                Button("Save & Load") {
                    vm.serverURLString = urlText.trimmingCharacters(in: .whitespacesAndNewlines)
                    vm.saveServerURL()
                    Task { await vm.loadCameras() }
                }
                .disabled(urlText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
            if vm.isLoading {
                ProgressView("Loading cameras…")
            }
            if let error = vm.error {
                Text(error).foregroundColor(.red)
            }
        }
        .onAppear { urlText = vm.serverURLString }
        .navigationTitle("Settings")
    }
}
