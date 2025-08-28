import SwiftUI
import AVKit

struct CameraGridView: View {
    @EnvironmentObject var vm: CamerasViewModel
    @Environment(\.horizontalSizeClass) private var hSize
    @State private var containerWidth: CGFloat = 0

    private func columns(for count: Int, width: CGFloat) -> [GridItem] {
        // Make an adaptive grid that picks reasonable cell sizes
        // Target ~180–220pt wide tiles; adjust as you like
        let target: CGFloat = hSize == .regular ? 240 : 200
        let n = max(1, Int(floor(width / target)))
        return Array(repeating: GridItem(.flexible(minimum: 140, maximum: 1000), spacing: 8), count: n)
    }

    var body: some View {
        GeometryReader { geo in
            ScrollView {
                LazyVGrid(columns: columns(for: vm.cameras.count, width: geo.size.width), spacing: 8) {
                    ForEach(vm.cameras) { cam in
                        ZStack(alignment: .bottomLeading) {
                            if let player = vm.gridPlayers[cam.id] {
                                PlayerView(player: player)
                                    .frame(height: 140)
                                    .clipped()
                                    .background(Color.black.opacity(0.9))
                                    .onTapGesture { vm.select(camera: cam) }
                                    .onDisappear { player.pause() } // avoid background decoding
                                    .onAppear {
                                        // If returning from detail, ensure muted autoplay continues
                                        if vm.selectedCamera == nil && player.timeControlStatus != .playing {
                                            player.play()
                                        }
                                    }
                            } else {
                                // Placeholder
                                Rectangle()
                                    .fill(Color.black.opacity(0.9))
                                    .frame(height: 140)
                                    .overlay(ProgressView())
                                    .onTapGesture { vm.select(camera: cam) }
                            }

                            Text(cam.name)
                                .font(.caption.weight(.semibold))
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .background(.ultraThinMaterial, in: Capsule())
                                .padding(6)
                        }
                        .cornerRadius(12)
                        .shadow(radius: 2, y: 1)
                    }
                }
                .padding(8)
            }
            .background(Color(.systemBackground))
            .onAppear { containerWidth = geo.size.width }
            .onChange(of: geo.size.width) { containerWidth = $0 }
        }
    }
}
