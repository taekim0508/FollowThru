import Foundation

// MARK: - AI Experience / Preferred-time enums

enum AIExperienceLevel: String, Codable, CaseIterable, Hashable {
    case beginner
    case intermediate
    case advanced

    var displayName: String { rawValue.capitalized }
}

enum AIPreferredTime: String, Codable, CaseIterable, Hashable {
    case morning
    case afternoon
    case evening
    case flexible

    var displayName: String { rawValue.capitalized }
}

struct AIRequestContext: Codable, Hashable {
    let experienceLevel: AIExperienceLevel
    let availableTime: Int
    let preferredTime: AIPreferredTime
}

// MARK: - AI Conversation types

enum AIConversationPhase: String, Hashable {
    case intake
    case confirming
    case preview
    case revising
    case created
}

struct AIConversationMessage: Identifiable, Hashable {
    enum Role: String, Codable, Hashable {
        case assistant
        case user
    }
    let id = UUID()
    let role: Role
    let text: String
}

struct AIConversationMessageDTO: Codable, Hashable {
    let role: AIConversationMessage.Role
    let content: String
}

extension AIConversationMessage {
    func toDTO() -> AIConversationMessageDTO {
        AIConversationMessageDTO(role: role, content: text)
    }
}

// MARK: - Intake DTOs

struct AIIntakeDraftDTO: Codable, Hashable {
    var goalSummary: String?       = nil
    var habitDescription: String?  = nil
    var frequency: String?         = nil
    var scheduleText: String?      = nil
    var scheduleDays: [String]     = []
    var durationMinutes: Int?      = nil
    var experienceLevel: AIExperienceLevel? = nil
    var category: String?          = nil  // free-form string; matches backend
    var preferredTime: AIPreferredTime = .flexible
    var availableTime: Int         = 15
    // Passively inferred — never explicitly asked
    var motivationStatement: String? = nil
    var habitType: String          = "binary"   // "binary" | "tracked"
    var targetValue: Double?       = nil
    var quantityUnit: String?      = nil
    var triggerValue: String?      = nil        // "HH:MM" extracted when user states a time
}

struct AIIntakeRequestDTO: Codable, Hashable {
    let recentMessages: [AIConversationMessageDTO]
    let currentDraft: AIIntakeDraftDTO
    let latestUserMessage: String
}

struct AIIntakeResponseDTO: Decodable, Hashable {
    let success: Bool
    let assistantMessage: String
    let updatedDraft: AIIntakeDraftDTO
    let missingFields: [String]
    let readyForConfirmation: Bool
    let confirmationSummary: String?
    let needsClarification: Bool
}

// MARK: - Habit Proposal / Candidate DTOs (two-variant proposal flow)

struct AIHabitProposalRequestDTO: Codable, Hashable {
    let recentMessages: [AIConversationMessageDTO]
    let latestUserMessage: String
}

struct AIHabitCandidateDTO: Codable, Hashable, Identifiable {
    let id = UUID()
    let title: String
    let category: String          // "fitness" | "wellness" | "study" | "reading" | "sleep"
    let description: String
    let suggestedSchedule: String
    let durationMinutes: Int
    let rationale: String
    let variant: String           // "balanced" | "ambitious"
    let habitPayload: HabitCreateRequestDTO
    let progressions: [AIProgressionDTO]

    private enum CodingKeys: String, CodingKey {
        case title, category, description, suggestedSchedule
        case durationMinutes, rationale, variant, habitPayload, progressions
    }
}

struct AIHabitProposalResponseDTO: Decodable, Hashable {
    let success: Bool
    let provider: String
    let model: String
    let action: String            // "clarify" | "propose" | "off_topic" | "sensitive"
    let assistantMessage: String
    let whatIHeard: String?
    let candidates: [AIHabitCandidateDTO]
    let needsClarification: Bool
}

struct AIRefineCandidateRequestDTO: Codable, Hashable {
    let idea: String
    let selectedCandidate: AIHabitCandidateDTO
    let refinement: String
    let recentMessages: [AIConversationMessageDTO]
}

struct AIRefineCandidateResponseDTO: Decodable, Hashable {
    let success: Bool
    let provider: String
    let model: String
    let assistantMessage: String
    let candidate: AIHabitCandidateDTO
}

struct AICreateCandidateRequestDTO: Codable, Hashable {
    let candidate: AIHabitCandidateDTO
}

// MARK: - Generate / Plan DTOs

struct AIGenerateRequestDTO: Codable, Hashable {
    let userGoal: String
    let category: String   // "fitness" | "study" | "wellness" | "reading" | "sleep"
    let context: AIRequestContext?
}

struct AIGenerateFromDraftRequestDTO: Codable, Hashable {
    let draft: AIIntakeDraftDTO
}

struct AIProgressionDTO: Codable, Hashable {
    let week: Int
    let description: String
}

// mirrors backend FrequencyPattern {"days": [...]}
struct BackendFrequencyPattern: Codable, Hashable {
    let days: [String]
}

struct HabitCreateRequestDTO: Codable, Hashable {
    let name: String
    let category: String
    let description: String
    let triggerType: String
    let triggerValue: String?
    let frequencyType: String
    let frequencyPattern: BackendFrequencyPattern?
    // "binary" (checkbox) or "tracked" (numeric goal)
    let habitType: String?
    // For tracked habits — the daily target quantity and its unit
    let targetValue: Double?
    let requiresQuantity: Bool
    let quantityUnit: String?
    let allowsNotes: Bool
    let motivationStatement: String?
}

struct AIPlanResponseDTO: Decodable, Hashable {
    let success: Bool
    let provider: String
    let model: String
    let habitPayload: HabitCreateRequestDTO
    let progressions: [AIProgressionDTO]
}

// The habit field in the create response — only fields we need after creation.
struct AICreatedHabitDTO: Decodable, Hashable {
    let id: Int
    let name: String
}

struct AICreateHabitResponseDTO: Decodable, Hashable {
    let success: Bool
    let provider: String
    let model: String
    let habit: AICreatedHabitDTO
    let habitPayload: HabitCreateRequestDTO
    let progressions: [AIProgressionDTO]
}

// MARK: - Revise Plan DTOs

struct AIPlanSnapshotDTO: Codable, Hashable {
    let habitPayload: HabitCreateRequestDTO
    let progressions: [AIProgressionDTO]
}

struct AIRevisePlanRequestDTO: Codable, Hashable {
    let draft: AIIntakeDraftDTO
    let currentPlan: AIPlanSnapshotDTO
    let critique: String
    let recentMessages: [AIConversationMessageDTO]
}

struct AIPlanPayloadResponseDTO: Decodable, Hashable {
    let provider: String
    let model: String
    let habitPayload: HabitCreateRequestDTO
    let progressions: [AIProgressionDTO]
}

struct AIRevisePlanResponseDTO: Decodable, Hashable {
    let success: Bool
    let provider: String
    let model: String
    let action: String  // "plan_tweak" | "reopen_intake"
    let planTweak: AIPlanPayloadResponseDTO?
    let reopenIntake: AIIntakeResponseDTO?
}

// MARK: - App-level AI plan preview (not persisted, lives in AppState)

struct AIPlanPreview: Identifiable, Hashable {
    let id = UUID()
    let provider: String
    let model: String
    let title: String
    let category: String
    let description: String
    let triggerValue: String?
    let frequencySummary: String
    let progressions: [AIProgressionDTO]
    let habitPayload: HabitCreateRequestDTO
}

// MARK: - Convenience extensions

extension HabitCreateRequestDTO {
    func toAIPlanPreview(provider: String, model: String, progressions: [AIProgressionDTO]) -> AIPlanPreview {
        AIPlanPreview(
            provider: provider,
            model: model,
            title: name,
            category: category,
            description: description,
            triggerValue: triggerValue,
            frequencySummary: BackendHabitMapper.frequencySummary(
                frequencyType: frequencyType,
                pattern: frequencyPattern
            ),
            progressions: progressions,
            habitPayload: self
        )
    }
}

extension AIPlanPayloadResponseDTO {
    func toAIPlanPreview() -> AIPlanPreview {
        habitPayload.toAIPlanPreview(
            provider: provider,
            model: model,
            progressions: progressions
        )
    }
}

extension AIPlanPreview {
    func toSnapshotDTO() -> AIPlanSnapshotDTO {
        AIPlanSnapshotDTO(habitPayload: habitPayload, progressions: progressions)
    }
}

// MARK: - Unified Chat DTOs

struct AIChatRequestDTO: Codable {
    let message: String
    let draft: AIIntakeDraftDTO
    let recentMessages: [AIConversationMessageDTO]
}

struct AIChatCandidateDTO: Codable, Identifiable {
    let id = UUID()
    let title: String
    let category: String
    let description: String
    let suggestedSchedule: String
    let durationMinutes: Int
    let rationale: String
    let variant: String                 // "balanced" | "ambitious"
    let habitPayload: HabitCreateRequestDTO
    let progressions: [AIProgressionDTO]

    private enum CodingKeys: String, CodingKey {
        case title, category, description, suggestedSchedule
        case durationMinutes, rationale, variant, habitPayload, progressions
    }
}

struct AIChatResponseDTO: Decodable {
    let action: String                  // "clarify" | "generate" | "advise" | "redirect"
    let assistantMessage: String
    let updatedDraft: AIIntakeDraftDTO
    let candidates: [AIChatCandidateDTO]
}

// MARK: - BackendHabitMapper (AI-relevant utilities only)

enum BackendHabitMapper {
    /// Parse "HH:MM" trigger value into a displayable Date.
    nonisolated static func time(from value: String) -> Date? {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "HH:mm"
        return formatter.date(from: value)
    }

    /// Human-readable frequency label for the plan preview card.
    nonisolated static func frequencySummary(
        frequencyType: String,
        pattern: BackendFrequencyPattern?
    ) -> String {
        if frequencyType.lowercased() == "daily" { return "Daily" }
        let labels = (pattern?.days ?? []).map { $0.prefix(3).capitalized }
        return labels.isEmpty ? "Custom" : labels.joined(separator: ", ")
    }
}
