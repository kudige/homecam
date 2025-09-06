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

        // The API may return camera URLs without a host section.  Patch any
        // relative URLs to include the host from the server base before
        // returning them to the caller.
        let patched = decoded.cameras.map { cam -> Camera in
            var newURLs: [String: URL] = [:]
            for (role, url) in cam.urls {
                if url.host == nil {
                    // Build an absolute URL using the server's base URL.
                    let absolute = URL(string: url.relativeString, relativeTo: serverBase)!.absoluteURL
                    newURLs[role] = absolute
                } else {
                    newURLs[role] = url
                }
            }
            return Camera(id: cam.id, name: cam.name, urls: newURLs)
        }

        return patched
    }
}
