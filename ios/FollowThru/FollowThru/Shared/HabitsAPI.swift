import Foundation

enum HabitsAPI {
    static func listHabits(status: String = "active") async throws -> [BackendHabit] {
        var components = URLComponents(url: BackendAPI.url("/api/habits/"), resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: "status_filter", value: status)]
        var request = try BackendAPI.request(path: "/api/habits/", method: "GET")
        request.url = components.url

        let (data, response) = try await BackendAPI.perform(request)
        if response.statusCode == 200 {
            return try BackendAPI.decodeResponse([BackendHabit].self, from: data)
        }
        throw BackendAPI.decodeError(data, response)
    }

    static func createHabit(_ payload: HabitCreateRequestDTO) async throws -> BackendHabit {
        let body = try BackendAPI.encoder().encode(payload)
        let request = try BackendAPI.request(path: "/api/habits/", method: "POST", body: body)
        let (data, response) = try await BackendAPI.perform(request)

        if response.statusCode == 201 {
            return try BackendAPI.decodeResponse(BackendHabit.self, from: data)
        }
        throw BackendAPI.decodeError(data, response)
    }
}

enum CompletionsAPI {
    static func completeHabit(habitID: Int, completedDate: String, note: String?) async throws -> BackendCompletion {
        let body = try BackendAPI.encoder().encode(
            CompletionCreateRequestDTO(
                completedDate: completedDate,
                quantityValue: nil,
                note: note
            )
        )
        let request = try BackendAPI.request(
            path: "/api/completions/habits/\(habitID)/complete",
            method: "POST",
            body: body
        )
        let (data, response) = try await BackendAPI.perform(request)

        if response.statusCode == 201 {
            return try BackendAPI.decodeResponse(BackendCompletion.self, from: data)
        }
        throw BackendAPI.decodeError(data, response)
    }

    static func listCompletions(habitID: Int) async throws -> [BackendCompletion] {
        let request = try BackendAPI.request(
            path: "/api/completions/habits/\(habitID)/completions",
            method: "GET"
        )
        let (data, response) = try await BackendAPI.perform(request)

        if response.statusCode == 200 {
            return try BackendAPI.decodeResponse([BackendCompletion].self, from: data)
        }
        throw BackendAPI.decodeError(data, response)
    }
}
