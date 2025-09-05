import Foundation

struct Camera: Identifiable, Decodable, Hashable {
    let id: String
    let name: String
    let urls: [String: URL]

    func url(for role: String) -> URL? {
        return urls[role]
    }
}

struct CameraListResponse: Decodable {
    let cameras: [Camera]
}
