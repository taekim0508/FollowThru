import Foundation

enum AIAPI {
    static func proposeHabits(_ payload: AIHabitProposalRequestDTO) async throws -> AIHabitProposalResponseDTO {
        let body = try BackendAPI.encoder().encode(payload)
        let request = try BackendAPI.request(path: "/api/ai/propose-habits", method: "POST", body: body)
        let (data, response) = try await BackendAPI.perform(request)

        if response.statusCode == 200 {
            return try BackendAPI.decodeResponse(AIHabitProposalResponseDTO.self, from: data)
        }
        throw BackendAPI.decodeError(data, response)
    }

    static func refineCandidate(_ payload: AIRefineCandidateRequestDTO) async throws -> AIRefineCandidateResponseDTO {
        let body = try BackendAPI.encoder().encode(payload)
        let request = try BackendAPI.request(path: "/api/ai/refine-candidate", method: "POST", body: body)
        let (data, response) = try await BackendAPI.perform(request)

        if response.statusCode == 200 {
            return try BackendAPI.decodeResponse(AIRefineCandidateResponseDTO.self, from: data)
        }
        throw BackendAPI.decodeError(data, response)
    }

    static func createCandidate(_ payload: AICreateCandidateRequestDTO) async throws -> AICreateHabitResponseDTO {
        let body = try BackendAPI.encoder().encode(payload)
        let request = try BackendAPI.request(path: "/api/ai/create-candidate", method: "POST", body: body)
        let (data, response) = try await BackendAPI.perform(request)

        if response.statusCode == 201 {
            return try BackendAPI.decodeResponse(AICreateHabitResponseDTO.self, from: data)
        }
        throw BackendAPI.decodeError(data, response)
    }

    static func intake(_ payload: AIIntakeRequestDTO) async throws -> AIIntakeResponseDTO {
        let body = try BackendAPI.encoder().encode(payload)
        let request = try BackendAPI.request(path: "/api/ai/intake", method: "POST", body: body)
        let (data, response) = try await BackendAPI.perform(request)

        if response.statusCode == 200 {
            return try BackendAPI.decodeResponse(AIIntakeResponseDTO.self, from: data)
        }
        throw BackendAPI.decodeError(data, response)
    }

    static func generatePlan(_ payload: AIGenerateRequestDTO) async throws -> AIPlanResponseDTO {
        let body = try BackendAPI.encoder().encode(payload)
        let request = try BackendAPI.request(path: "/api/ai/generate-plan", method: "POST", body: body)
        let (data, response) = try await BackendAPI.perform(request)

        if response.statusCode == 200 {
            return try BackendAPI.decodeResponse(AIPlanResponseDTO.self, from: data)
        }
        throw BackendAPI.decodeError(data, response)
    }

    static func generateAndCreate(_ payload: AIGenerateRequestDTO) async throws -> AICreateHabitResponseDTO {
        let body = try BackendAPI.encoder().encode(payload)
        let request = try BackendAPI.request(path: "/api/ai/generate-and-create", method: "POST", body: body)
        let (data, response) = try await BackendAPI.perform(request)

        if response.statusCode == 201 {
            return try BackendAPI.decodeResponse(AICreateHabitResponseDTO.self, from: data)
        }
        throw BackendAPI.decodeError(data, response)
    }

    static func generatePlan(from draft: AIIntakeDraftDTO) async throws -> AIPlanResponseDTO {
        let body = try BackendAPI.encoder().encode(AIGenerateFromDraftRequestDTO(draft: draft))
        let request = try BackendAPI.request(path: "/api/ai/generate-plan-from-draft", method: "POST", body: body)
        let (data, response) = try await BackendAPI.perform(request)

        if response.statusCode == 200 {
            return try BackendAPI.decodeResponse(AIPlanResponseDTO.self, from: data)
        }
        throw BackendAPI.decodeError(data, response)
    }

    static func generateAndCreate(from draft: AIIntakeDraftDTO) async throws -> AICreateHabitResponseDTO {
        let body = try BackendAPI.encoder().encode(AIGenerateFromDraftRequestDTO(draft: draft))
        let request = try BackendAPI.request(path: "/api/ai/generate-and-create-from-draft", method: "POST", body: body)
        let (data, response) = try await BackendAPI.perform(request)

        if response.statusCode == 201 {
            return try BackendAPI.decodeResponse(AICreateHabitResponseDTO.self, from: data)
        }
        throw BackendAPI.decodeError(data, response)
    }

    static func revisePlan(_ payload: AIRevisePlanRequestDTO) async throws -> AIRevisePlanResponseDTO {
        let body = try BackendAPI.encoder().encode(payload)
        let request = try BackendAPI.request(path: "/api/ai/revise-plan", method: "POST", body: body)
        let (data, response) = try await BackendAPI.perform(request)

        if response.statusCode == 200 {
            return try BackendAPI.decodeResponse(AIRevisePlanResponseDTO.self, from: data)
        }
        throw BackendAPI.decodeError(data, response)
    }

    // MARK: - Unified chat endpoint

    static func chat(_ payload: AIChatRequestDTO) async throws -> AIChatResponseDTO {
        let body = try BackendAPI.encoder().encode(payload)
        let request = try BackendAPI.request(path: "/api/ai/chat", method: "POST", body: body)
        let (data, response) = try await BackendAPI.perform(request)

        if response.statusCode == 200 {
            return try BackendAPI.decodeResponse(AIChatResponseDTO.self, from: data)
        }
        throw BackendAPI.decodeError(data, response)
    }
}
