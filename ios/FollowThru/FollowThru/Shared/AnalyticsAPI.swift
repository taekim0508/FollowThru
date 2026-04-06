//
//  AnalyticsAPI.swift
//  FollowThru
//
//  Created by Ronnie Yalung on 3/25/26.
//
import Foundation

// MARK: - Analytics Models

struct BinaryAnalytics: Codable {
    let habitId: Int
    let habitName: String
    let habitType: String
    let period: String
    let startDate: String
    let endDate: String

    // stats
    let currentStreak: Int
    let maxStreak: Int
    let completionRate: Double
    let totalCompletions: Int
    let scheduledDays: Int

    // chart
    let bars: [BinaryBar]
}

struct BinaryBar: Codable, Identifiable {
    var id: String { date ?? label }
    let date: String?
    let label: String
    let isComplete: Bool
    let isScheduled: Bool
    let isFuture: Bool

    // for grouped bars (year/all)
    let weekStart: String?
    let weekEnd: String?
    let monthStart: String?
    let monthEnd: String?
    let completedCount: Int?
    let scheduledCount: Int?
    let color: String?  // "grey" | "orange" | "green"
}

struct TrackedAnalytics: Codable {
    let habitId: Int
    let habitName: String
    let habitType: String
    let quantityUnit: String?
    let targetValue: Double?
    let period: String
    let startDate: String
    let endDate: String

    // stats
    let currentStreak: Int
    let maxStreak: Int
    let completionRate: Double
    let totalValue: Double?
    let dailyAverage: Double?
    let personalBest: Double?
    let scheduledDays: Int
    let completedDays: Int

    // chart
    let bars: [TrackedBar]
}

struct TrackedBar: Codable, Identifiable {
    var id: String { date ?? label }
    let date: String?
    let label: String
    let value: Double?
    let isComplete: Bool?
    let isScheduled: Bool?
    let isFuture: Bool
    let targetValue: Double?

    // for grouped bars (year/all)
    let weekStart: String?
    let weekEnd: String?
    let monthStart: String?
    let monthEnd: String?
    let totalValue: Double?
    let completedCount: Int?
    let scheduledCount: Int?
    let color: String?
}

// MARK: - API Client

enum AnalyticsAPI {

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

    private static func decodeError(_ data: Data?, _ response: URLResponse?) -> AnalyticsAPIError {
        guard let data = data,
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            if let http = response as? HTTPURLResponse {
                return .httpStatus(http.statusCode)
            }
            return .unknown
        }
        if let detail = json["detail"] as? String { return .message(detail) }
        if let http = response as? HTTPURLResponse { return .httpStatus(http.statusCode) }
        return .unknown
    }

    static func binaryAnalytics(habitId: Int) async throws -> BinaryAnalytics {
        guard let token = TokenStore.get() else { throw AnalyticsAPIError.notAuthenticated }
        var req = URLRequest(url: url("/api/habits/\(habitId)/analytics/binary"))
        req.httpMethod = "GET"
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw AnalyticsAPIError.unknown }
        if http.statusCode == 401 { TokenStore.clear(); throw AnalyticsAPIError.notAuthenticated }
        if http.statusCode == 200 { return try jsonDecoder.decode(BinaryAnalytics.self, from: data) }
        throw decodeError(data, response)
    }

    static func trackedAnalytics(habitId: Int) async throws -> TrackedAnalytics {
        guard let token = TokenStore.get() else { throw AnalyticsAPIError.notAuthenticated }
        var req = URLRequest(url: url("/api/habits/\(habitId)/analytics/tracked"))
        req.httpMethod = "GET"
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw AnalyticsAPIError.unknown }
        if http.statusCode == 401 { TokenStore.clear(); throw AnalyticsAPIError.notAuthenticated }
        if http.statusCode == 200 { return try jsonDecoder.decode(TrackedAnalytics.self, from: data) }
        throw decodeError(data, response)
    }
}

enum AnalyticsAPIError: LocalizedError {
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
