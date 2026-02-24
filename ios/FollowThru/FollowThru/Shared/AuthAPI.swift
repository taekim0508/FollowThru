import Foundation

// MARK: - Token storage
enum TokenStore {
    private static let key = "followthru_access_token"

    static func save(_ token: String) {
        UserDefaults.standard.set(token, forKey: key)
    }

    static func get() -> String? {
        UserDefaults.standard.string(forKey: key)
    }

    static func clear() {
        UserDefaults.standard.removeObject(forKey: key)
    }

    /// True if we have a token (does not validate it; use getMe() for that).
    static var hasToken: Bool { TokenStore.get() != nil }
}

// MARK: - API base URL
//
// Simulator: use "http://127.0.0.1:8000" to hit a server on your Mac.
// Physical device: use your Mac's LAN IP, e.g. "http://192.168.1.10:8000".
// If you use HTTP (not HTTPS), add an ATS exception in Info.plist.
enum API {
    static var baseURL: String {
        #if DEBUG
        return ProcessInfo.processInfo.environment["API_BASE_URL"] ?? "http://127.0.0.1:8000"
        #else
        return ProcessInfo.processInfo.environment["API_BASE_URL"] ?? "https://your-production-host.com"
        #endif
    }
}

// MARK: - DTOs (backend JSON shape)
private struct BackendUser: Decodable {
    let id: Int
    let email: String
    let name: String?
    let created_at: String?
}

private struct AuthResponse: Decodable {
    let user: BackendUser
    let access_token: String
    let token_type: String
}

/// Map backend user to app User (id as String, name → username).
fileprivate func user(from backend: BackendUser) -> User {
    User(
        id: String(backend.id),
        email: backend.email,
        username: backend.name ?? backend.email.split(separator: "@").first.map(String.init) ?? "User"
    )
}

// MARK: - Auth API client
enum AuthAPI {
    private static let session: URLSession = {
        let c = URLSessionConfiguration.default
        c.timeoutIntervalForRequest = 30
        return URLSession(configuration: c)
    }()

    private static func url(_ path: String) -> URL {
        URL(string: API.baseURL + path)!
    }

    private static func decodeError(_ data: Data?, _ response: URLResponse?) -> AuthAPIError {
        guard let data = data,
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            if let http = response as? HTTPURLResponse {
                return .httpStatus(http.statusCode)
            }
            return .unknown
        }

        // FastAPI can return either:
        // - {"detail": "some message"}
        // - {"detail": [ { "msg": "...", ... }, ... ]}
        if let detailString = json["detail"] as? String {
            return .message(detailString)
        }

        if let detailArray = json["detail"] as? [[String: Any]],
           let first = detailArray.first {
            if let msg = first["msg"] as? String {
                return .message(msg)
            }
        }

        if let http = response as? HTTPURLResponse {
            return .httpStatus(http.statusCode)
        }
        return .unknown
    }

    /// POST /api/auth/register
    static func register(email: String, password: String, name: String?) async throws -> (user: User, token: String) {
        let body: [String: Any] = [
            "email": email,
            "password": password,
            "name": name as Any
        ].compactMapValues { $0 }
        var req = URLRequest(url: url("/api/auth/register"))
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw AuthAPIError.unknown }

        if http.statusCode == 201,
           let decoded = try? JSONDecoder().decode(AuthResponse.self, from: data) {
            return (user(from: decoded.user), decoded.access_token)
        }
        throw decodeError(data, response)
    }

    /// POST /api/auth/login
    static func login(email: String, password: String) async throws -> (user: User, token: String) {
        let body: [String: Any] = ["email": email, "password": password]
        var req = URLRequest(url: url("/api/auth/login"))
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw AuthAPIError.unknown }

        if http.statusCode == 200,
           let decoded = try? JSONDecoder().decode(AuthResponse.self, from: data) {
            return (user(from: decoded.user), decoded.access_token)
        }
        throw decodeError(data, response)
    }

    /// GET /api/auth/me — requires stored token.
    static func getMe() async throws -> User {
        guard let token = TokenStore.get() else { throw AuthAPIError.notAuthenticated }
        var req = URLRequest(url: url("/api/auth/me"))
        req.httpMethod = "GET"
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw AuthAPIError.unknown }

        if http.statusCode == 200,
           let backend = try? JSONDecoder().decode(BackendUser.self, from: data) {
            return user(from: backend)
        }
        if http.statusCode == 401 {
            TokenStore.clear()
            throw AuthAPIError.notAuthenticated
        }
        throw decodeError(data, response)
    }

    /// PATCH /api/auth/me — only include keys you want to update.
    static func updateMe(name: String? = nil, email: String? = nil, currentPassword: String? = nil, newPassword: String? = nil) async throws -> User {
        guard let token = TokenStore.get() else { throw AuthAPIError.notAuthenticated }
        var body = [String: Any]()
        if let v = name { body["name"] = v }
        if let v = email { body["email"] = v }
        if let v = currentPassword { body["current_password"] = v }
        if let v = newPassword { body["new_password"] = v }
        if body.isEmpty { throw AuthAPIError.message("No fields to update") }

        var req = URLRequest(url: url("/api/auth/me"))
        req.httpMethod = "PATCH"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        req.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw AuthAPIError.unknown }

        if http.statusCode == 200,
           let backend = try? JSONDecoder().decode(BackendUser.self, from: data) {
            return user(from: backend)
        }
        if http.statusCode == 401 {
            // 401 from PATCH /me can mean invalid token OR wrong current_password. Only clear token for invalid auth.
            let detailMessage = detailString(from: data)
            let isPasswordError = detailMessage?.lowercased().contains("current_password") == true
                || detailMessage?.lowercased().contains("password") == true
            if isPasswordError, let msg = detailMessage {
                throw AuthAPIError.message(msg)
            }
            TokenStore.clear()
            throw AuthAPIError.notAuthenticated
        }
        throw decodeError(data, response)
    }
}

/// Extract backend "detail" as a single string (for 401 handling).
private func detailString(from data: Data?) -> String? {
    guard let data = data,
          let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return nil }
    if let s = json["detail"] as? String { return s }
    if let arr = json["detail"] as? [[String: Any]], let first = arr.first, let msg = first["msg"] as? String {
        return msg
    }
    return nil
}

// MARK: - Errors
enum AuthAPIError: LocalizedError {
    case notAuthenticated
    case message(String)
    case httpStatus(Int)
    case unknown

    var errorDescription: String? {
        switch self {
        case .notAuthenticated: return "Not logged in"
        case .message(let s): return s
        case .httpStatus(let c): return "Request failed (\(c))"
        case .unknown: return "Something went wrong"
        }
    }
}
