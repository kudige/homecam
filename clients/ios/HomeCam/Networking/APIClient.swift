import Foundation

final class APIClient {
    static let shared = APIClient()

    private init() {}

    func fetchCameras(serverBase: URL) async throws -> [Camera] {
        // Expecting: GET {serverBase}/api/cameras -> { "cameras": [ {id,name,urls:{role:url,...}}, ... ] }
        let url = serverBase.appendingPathComponent("api/cameras")
        var req = URLRequest(url: url)
        req.timeoutInterval = 15

        let (data, resp) = try await URLSession.shared.data(for: req)
        guard let http = resp as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        let decoded = try JSONDecoder().decode(CameraListResponse.self, from: data)
        return decoded.cameras
    }
}
