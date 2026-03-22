import Foundation

enum CommunityAPI {
    private static let session: URLSession = {
        let c = URLSessionConfiguration.default
        c.timeoutIntervalForRequest = 30
        return URLSession(configuration: c)
    }()

    private static var jsonDecoder: JSONDecoder {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }

    private static func url(_ path: String) -> URL {
        URL(string: API.baseURL + path)!
    }

    private static func decodeError(_ data: Data?, _ response: URLResponse?) -> CommunityAPIError {
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
           let msg = first["msg"] as? String {
            return .message(msg)
        }
        if let http = response as? HTTPURLResponse {
            return .httpStatus(http.statusCode)
        }
        return .unknown
    }

    private static func authorizedGET(_ path: String) async throws -> (Data, HTTPURLResponse) {
        guard let token = TokenStore.get() else { throw CommunityAPIError.notAuthenticated }
        var req = URLRequest(url: url(path))
        req.httpMethod = "GET"
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw CommunityAPIError.unknown }
        if http.statusCode == 401 {
            TokenStore.clear()
            throw CommunityAPIError.notAuthenticated
        }
        return (data, http)
    }

    private static func authorizedPOST(_ path: String, body: [String: Any]? = nil) async throws -> (Data, HTTPURLResponse) {
        guard let token = TokenStore.get() else { throw CommunityAPIError.notAuthenticated }
        var req = URLRequest(url: url(path))
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        if let body = body {
            req.httpBody = try JSONSerialization.data(withJSONObject: body)
        }
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw CommunityAPIError.unknown }
        if http.statusCode == 401 {
            TokenStore.clear()
            throw CommunityAPIError.notAuthenticated
        }
        return (data, http)
    }

    private static func authorizedDELETE(_ path: String) async throws -> (Data, HTTPURLResponse) {
        guard let token = TokenStore.get() else { throw CommunityAPIError.notAuthenticated }
        var req = URLRequest(url: url(path))
        req.httpMethod = "DELETE"
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw CommunityAPIError.unknown }
        if http.statusCode == 401 {
            TokenStore.clear()
            throw CommunityAPIError.notAuthenticated
        }
        return (data, http)
    }

    // MARK: - Friends

    static func searchUsers(query: String) async throws -> [UserSearchResult] {
        var c = URLComponents(string: API.baseURL + "/api/friends/search")!
        c.queryItems = [URLQueryItem(name: "q", value: query)]
        guard let u = c.url else { throw CommunityAPIError.unknown }
        guard let token = TokenStore.get() else { throw CommunityAPIError.notAuthenticated }
        var req = URLRequest(url: u)
        req.httpMethod = "GET"
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw CommunityAPIError.unknown }
        if http.statusCode == 401 {
            TokenStore.clear()
            throw CommunityAPIError.notAuthenticated
        }
        if http.statusCode == 200 {
            return try jsonDecoder.decode([UserSearchResult].self, from: data)
        }
        throw decodeError(data, response)
    }

    static func inboxDetail() async throws -> [FriendInboxItem] {
        let (data, http) = try await authorizedGET("/api/friends/requests/inbox/detail")
        if http.statusCode == 200 {
            return try jsonDecoder.decode([FriendInboxItem].self, from: data)
        }
        throw decodeError(data, http)
    }

    static func sendFriendRequest(receiverId: Int, message: String? = nil) async throws {
        var c = URLComponents(string: API.baseURL + "/api/friends/requests")!
        var items = [URLQueryItem(name: "receiver_id", value: String(receiverId))]
        if let message = message, !message.isEmpty {
            items.append(URLQueryItem(name: "message", value: message))
        }
        c.queryItems = items
        guard let u = c.url else { throw CommunityAPIError.unknown }
        guard let token = TokenStore.get() else { throw CommunityAPIError.notAuthenticated }
        var req = URLRequest(url: u)
        req.httpMethod = "POST"
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw CommunityAPIError.unknown }
        if http.statusCode == 401 {
            TokenStore.clear()
            throw CommunityAPIError.notAuthenticated
        }
        if http.statusCode == 201 { return }
        throw decodeError(data, response)
    }

    static func acceptFriendRequest(requestId: Int) async throws {
        let (data, http) = try await authorizedPOST("/api/friends/requests/\(requestId)/accept")
        if http.statusCode == 200 { return }
        throw decodeError(data, http)
    }

    static func declineFriendRequest(requestId: Int) async throws {
        let (data, http) = try await authorizedPOST("/api/friends/requests/\(requestId)/decline")
        if http.statusCode == 200 { return }
        throw decodeError(data, http)
    }

    static func friendsDetail() async throws -> [FriendProfile] {
        let (data, http) = try await authorizedGET("/api/friends/list/detail")
        if http.statusCode == 200 {
            return try jsonDecoder.decode([FriendProfile].self, from: data)
        }
        throw decodeError(data, http)
    }

    // MARK: - Feed

    static func feed(limit: Int = 30) async throws -> [FeedPost] {
        var c = URLComponents(string: API.baseURL + "/api/community/feed")!
        c.queryItems = [URLQueryItem(name: "limit", value: String(limit))]
        guard let u = c.url else { throw CommunityAPIError.unknown }
        guard let token = TokenStore.get() else { throw CommunityAPIError.notAuthenticated }
        var req = URLRequest(url: u)
        req.httpMethod = "GET"
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw CommunityAPIError.unknown }
        if http.statusCode == 401 {
            TokenStore.clear()
            throw CommunityAPIError.notAuthenticated
        }
        if http.statusCode == 200 {
            return try jsonDecoder.decode([FeedPost].self, from: data)
        }
        throw decodeError(data, response)
    }

    static func likePost(postId: Int) async throws {
        let (data, http) = try await authorizedPOST("/api/community/posts/\(postId)/like")
        if http.statusCode == 201 { return }
        if http.statusCode == 200 { return }
        throw decodeError(data, http)
    }

    static func unlikePost(postId: Int) async throws {
        let (data, http) = try await authorizedDELETE("/api/community/posts/\(postId)/like")
        if http.statusCode == 200 { return }
        throw decodeError(data, http)
    }

    static func comments(postId: Int) async throws -> [CommentItem] {
        let (data, http) = try await authorizedGET("/api/community/posts/\(postId)/comments")
        if http.statusCode == 200 {
            return try jsonDecoder.decode([CommentItem].self, from: data)
        }
        throw decodeError(data, http)
    }

    static func addComment(postId: Int, text: String) async throws -> CommentItem {
        let (data, http) = try await authorizedPOST("/api/community/posts/\(postId)/comments", body: ["body": text])
        if http.statusCode == 201 {
            return try jsonDecoder.decode(CommentItem.self, from: data)
        }
        throw decodeError(data, http)
    }
}

enum CommunityAPIError: LocalizedError {
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
