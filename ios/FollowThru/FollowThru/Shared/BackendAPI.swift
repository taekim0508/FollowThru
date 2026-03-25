import Foundation

enum BackendAPIError: LocalizedError {
    case notAuthenticated
    case message(String)
    case httpStatus(Int)
    case unknown

    var errorDescription: String? {
        switch self {
        case .notAuthenticated:
            return "Not logged in"
        case .message(let message):
            return message
        case .httpStatus(let statusCode):
            return "Request failed (\(statusCode))"
        case .unknown:
            return "Something went wrong"
        }
    }
}

enum BackendAPI {
    static let session: URLSession = {
        let configuration = URLSessionConfiguration.default
        configuration.timeoutIntervalForRequest = 30
        return URLSession(configuration: configuration)
    }()

    static func url(_ path: String) -> URL {
        URL(string: API.baseURL + path)!
    }

    static func encoder() -> JSONEncoder {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        return encoder
    }

    static func decoder() -> JSONDecoder {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return decoder
    }

    static func request(path: String, method: String, body: Data? = nil, requiresAuth: Bool = true) throws -> URLRequest {
        var request = URLRequest(url: url(path))
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if requiresAuth {
            guard let token = TokenStore.get() else {
                throw BackendAPIError.notAuthenticated
            }
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        request.httpBody = body
        return request
    }

    static func perform(_ request: URLRequest) async throws -> (Data, HTTPURLResponse) {
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw BackendAPIError.unknown
        }
        if http.statusCode == 401 {
            TokenStore.clear()
            throw BackendAPIError.notAuthenticated
        }
        return (data, http)
    }

    static func decodeError(_ data: Data?, _ response: URLResponse?) -> BackendAPIError {
        guard let data = data,
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            if let http = response as? HTTPURLResponse {
                return .httpStatus(http.statusCode)
            }
            return .unknown
        }

        if let detailString = json["detail"] as? String {
            return .message(detailString)
        }

        if let detailArray = json["detail"] as? [[String: Any]],
           let first = detailArray.first,
           let message = first["msg"] as? String {
            return .message(message)
        }

        if let http = response as? HTTPURLResponse {
            return .httpStatus(http.statusCode)
        }
        return .unknown
    }

    static func decodeResponse<T: Decodable>(_ type: T.Type, from data: Data) throws -> T {
        try decoder().decode(T.self, from: data)
    }
}
