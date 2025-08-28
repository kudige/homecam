import Foundation

struct Camera: Identifiable, Decodable, Hashable {
    let id: String
    let name: String
    let lowURL: URL
    let highURL: URL

    enum CodingKeys: String, CodingKey {
        case id, name
        case lowURL = "low_url"
        case highURL = "high_url"
    }
}

struct CameraListResponse: Decodable {
    let cameras: [Camera]
}
