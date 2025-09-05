import SwiftUI
import AVKit

struct CameraDetailView: View {
    let camera: Camera
    let onClose: () -> Void

    @State private var player: AVPlayer? = nil

    var body: some View {
        NavigationStack {
            ZStack {
                if let p = player {
                    VideoPlayer(player: p)
                        .ignoresSafeArea()
                        .onAppear { p.play() }
                        .onDisappear { p.pause() }
                } else {
                    ProgressView("Loading high-res…")
                }
            }
            .navigationTitle(camera.name)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close") {
                        onClose()
                    }
                }
            }
        }
        .onAppear {
            // Build the high-res player fresh (keeps grid paused)
            if let url = camera.urls["high"] ?? camera.urls["medium"] ?? camera.urls["grid"] {
                let p = AVPlayer(url: url)
                p.automaticallyWaitsToMinimizeStalling = true
                p.isMuted = false
                player = p
            }
        }
        .onDisappear {
            player?.pause()
            player = nil
        }
    }
}
