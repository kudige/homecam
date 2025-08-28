import Foundation
import AVKit
import SwiftUI

@MainActor
final class CamerasViewModel: ObservableObject {
    @Published var serverURLString: String = UserDefaults.standard.string(forKey: "serverURL") ?? ""
    @Published var cameras: [Camera] = []
    @Published var gridPlayers: [String: AVPlayer] = [:]   // camera.id -> player
    @Published var isLoading = false
    @Published var error: String?
    @Published var selectedCamera: Camera? = nil

    // Derived convenience
    var serverURL: URL? { URL(string: serverURLString) }

    func saveServerURL() {
        UserDefaults.standard.set(serverURLString, forKey: "serverURL")
    }

    func loadCameras() async {
        guard let base = serverURL else {
            self.error = "Invalid server URL."
            return
        }
        isLoading = true
        error = nil
        do {
            let cams = try await APIClient.shared.fetchCameras(serverBase: base)
            self.cameras = cams
            await setupGridPlayers(for: cams)
        } catch {
            self.error = "Failed to load cameras: \(error.localizedDescription)"
        }
        isLoading = false
    }

    private func setupGridPlayers(for cams: [Camera]) async {
        // Tear down any old players
        pauseAll()
        gridPlayers.removeAll()

        for cam in cams {
            let p = AVPlayer(url: cam.lowURL)
            p.isMuted = true
            // Auto-play
            p.play()
            gridPlayers[cam.id] = p
        }
    }

    func pauseAll() {
        for (_, p) in gridPlayers {
            p.pause()
        }
    }

    func resumeAll() {
        for (_, p) in gridPlayers {
            // Prevent double-starting if already playing
            if p.timeControlStatus != .playing {
                p.play()
            }
        }
    }

    func select(camera: Camera) {
        // Pause grid and show detail
        pauseAll()
        selectedCamera = camera
    }

    func deselectCamera() {
        selectedCamera = nil
        // Resume grid after closing detail
        resumeAll()
    }

    // App lifecycle hooks
    func appWentInactive() { pauseAll() }
    func appBecameActive() {
        if selectedCamera == nil { resumeAll() }
    }
}

