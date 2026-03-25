//
//  HabitsAPI.swift
//  FollowThru
//
//  Created by Ronnie Yalung on 3/24/26.
//


import Foundation

enum HabitsAPI {

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

    private static func decodeError(_ data: Data?, _ response: URLResponse?) -> HabitsAPIError {
        guard let data = data,
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            if let http = response as? HTTPURLResponse {
                return .httpStatus(http.statusCode)
            }
            return .unknown
        }
        if let detail = json["detail"] as? String {
            return .message(detail)
        }
        if let http = response as? HTTPURLResponse {
            return .httpStatus(http.statusCode)
        }
        return .unknown
    }

    private static func authorizedRequest(
        _ path: String,
        method: String,
        body: [String: Any]? = nil
    ) throws -> URLRequest {
        guard let token = TokenStore.get() else { throw HabitsAPIError.notAuthenticated }
        var req = URLRequest(url: url(path))
        req.httpMethod = method
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        if let body = body {
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = try JSONSerialization.data(withJSONObject: body)
        }
        return req
    }

    // MARK: - Habits

    static func listHabits() async throws -> [Habit] {
        let req = try authorizedRequest("/api/habits/", method: "GET")
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw HabitsAPIError.unknown }
        if http.statusCode == 401 { TokenStore.clear(); throw HabitsAPIError.notAuthenticated }
        if http.statusCode == 200 { return try jsonDecoder.decode([Habit].self, from: data) }
        throw decodeError(data, response)
    }

    static func createHabit(
        name: String,
        description: String,
        category: String,
        habitType: String,
        targetValue: Double?,
        quantityUnit: String?,
        triggerValue: String,
        frequencyPattern: [String: [String]]
    ) async throws -> Habit {
        var body: [String: Any] = [
            "name": name,
            "description": description,
            "category": category,
            "habit_type": habitType,
            "trigger_type": "time",
            "trigger_value": triggerValue,
            "frequency_pattern": frequencyPattern,
        ]
        if let tv = targetValue { body["target_value"] = tv }
        if let qu = quantityUnit { body["quantity_unit"] = qu }

        let req = try authorizedRequest("/api/habits/", method: "POST", body: body)
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw HabitsAPIError.unknown }
        if http.statusCode == 401 { TokenStore.clear(); throw HabitsAPIError.notAuthenticated }
        if http.statusCode == 201 { return try jsonDecoder.decode(Habit.self, from: data) }
        throw decodeError(data, response)
    }

    static func updateHabit(
        id: Int,
        name: String? = nil,
        description: String? = nil,
        triggerValue: String? = nil,
        frequencyPattern: [String: [String]]? = nil,
        habitType: String? = nil,
        targetValue: Double? = nil,
        quantityUnit: String? = nil,
        status: String? = nil
    ) async throws -> Habit {
        var body: [String: Any] = [:]
        if let v = name { body["name"] = v }
        if let v = description { body["description"] = v }
        if let v = triggerValue { body["trigger_value"] = v }
        if let v = frequencyPattern { body["frequency_pattern"] = v }
        if let v = habitType { body["habit_type"] = v }
        if let v = targetValue { body["target_value"] = v }
        if let v = quantityUnit { body["quantity_unit"] = v }
        if let v = status { body["status"] = v }

        let req = try authorizedRequest("/api/habits/\(id)", method: "PUT", body: body)
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw HabitsAPIError.unknown }
        if http.statusCode == 401 { TokenStore.clear(); throw HabitsAPIError.notAuthenticated }
        if http.statusCode == 200 { return try jsonDecoder.decode(Habit.self, from: data) }
        throw decodeError(data, response)
    }

    static func deleteHabit(id: Int) async throws {
        let req = try authorizedRequest("/api/habits/\(id)", method: "DELETE")
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw HabitsAPIError.unknown }
        if http.statusCode == 401 { TokenStore.clear(); throw HabitsAPIError.notAuthenticated }
        if http.statusCode == 204 { return }
        throw decodeError(data, response)
    }

    static func checkStreaks() async throws -> [Habit] {
        let req = try authorizedRequest("/api/habits/check-streaks", method: "POST")
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw HabitsAPIError.unknown }
        if http.statusCode == 401 { TokenStore.clear(); throw HabitsAPIError.notAuthenticated }
        if http.statusCode == 200 { return try jsonDecoder.decode([Habit].self, from: data) }
        throw decodeError(data, response)
    }

    // MARK: - Completions

    static func completeHabit(
        habitId: Int,
        completedDate: String,
        progressValue: Double? = nil,
        note: String? = nil
    ) async throws -> CompletionResponse {
        var body: [String: Any] = ["completed_date": completedDate]
        if let pv = progressValue { body["progress_value"] = pv }
        if let n = note { body["note"] = n }

        let req = try authorizedRequest(
            "/api/completions/habits/\(habitId)/complete",
            method: "POST",
            body: body
        )
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw HabitsAPIError.unknown }
        if http.statusCode == 401 { TokenStore.clear(); throw HabitsAPIError.notAuthenticated }
        if http.statusCode == 201 { return try jsonDecoder.decode(CompletionResponse.self, from: data) }
        throw decodeError(data, response)
    }

    static func updateProgress(
        habitId: Int,
        completedDate: String,
        progressValue: Double,
        note: String? = nil
    ) async throws -> CompletionResponse {
        var body: [String: Any] = [
            "completed_date": completedDate,
            "progress_value": progressValue,
        ]
        if let n = note { body["note"] = n }

        let req = try authorizedRequest(
            "/api/completions/habits/\(habitId)/progress",
            method: "PATCH",
            body: body
        )
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw HabitsAPIError.unknown }
        if http.statusCode == 401 { TokenStore.clear(); throw HabitsAPIError.notAuthenticated }
        if http.statusCode == 200 { return try jsonDecoder.decode(CompletionResponse.self, from: data) }
        throw decodeError(data, response)
    }

    static func listCompletions(habitId: Int) async throws -> [HabitLog] {
        let req = try authorizedRequest(
            "/api/completions/habits/\(habitId)/completions",
            method: "GET"
        )
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw HabitsAPIError.unknown }
        if http.statusCode == 401 { TokenStore.clear(); throw HabitsAPIError.notAuthenticated }
        if http.statusCode == 200 { return try jsonDecoder.decode([HabitLog].self, from: data) }
        throw decodeError(data, response)
    }
}

// MARK: - Errors
enum HabitsAPIError: LocalizedError {
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