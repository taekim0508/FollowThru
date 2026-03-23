import Foundation

enum AIExperienceLevel: String, Codable, CaseIterable, Hashable {
    case beginner
    case intermediate
    case advanced

    var displayName: String {
        rawValue.capitalized
    }
}

enum AIPreferredTime: String, Codable, CaseIterable, Hashable {
    case morning
    case afternoon
    case evening
    case flexible

    var displayName: String {
        rawValue.capitalized
    }
}

struct AIRequestContext: Codable, Hashable {
    let experienceLevel: AIExperienceLevel
    let availableTime: Int
    let preferredTime: AIPreferredTime
}

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

struct AIIntakeDraftDTO: Codable, Hashable {
    var goalSummary: String? = nil
    var habitDescription: String? = nil
    var frequency: String? = nil
    var scheduleText: String? = nil
    var scheduleDays: [String] = []
    var durationMinutes: Int? = nil
    var experienceLevel: AIExperienceLevel? = nil
    var category: HabitCategory? = nil
    var preferredTime: AIPreferredTime = .flexible
    var availableTime: Int = 15
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

struct AIGenerateFromDraftRequestDTO: Codable, Hashable {
    let draft: AIIntakeDraftDTO
}

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
    let action: String
    let planTweak: AIPlanPayloadResponseDTO?
    let reopenIntake: AIIntakeResponseDTO?
}

struct AIGenerateRequestDTO: Codable, Hashable {
    let userGoal: String
    let category: HabitCategory
    let context: AIRequestContext?
}

struct BackendFrequencyPattern: Codable, Hashable {
    let days: [String]
}

struct HabitCreateRequestDTO: Codable, Hashable {
    let name: String
    let category: HabitCategory
    let description: String
    let triggerType: String
    let triggerValue: String
    let frequencyType: String
    let frequencyPattern: BackendFrequencyPattern?
    let requiresQuantity: Bool
    let quantityUnit: String?
    let allowsNotes: Bool
    let motivationStatement: String?
}

struct BackendHabit: Decodable, Identifiable, Hashable {
    let id: Int
    let userId: Int
    let name: String
    let category: HabitCategory
    let description: String
    let triggerType: String
    let triggerValue: String
    let frequencyType: String
    let frequencyPattern: BackendFrequencyPattern?
    let requiresQuantity: Bool
    let quantityUnit: String?
    let allowsNotes: Bool
    let motivationStatement: String?
    let status: String
    let createdAt: String
    let startedAt: String?
    let updatedAt: String?
}

struct CompletionCreateRequestDTO: Codable, Hashable {
    let completedDate: String
    let quantityValue: Double?
    let note: String?
}

struct BackendCompletion: Decodable, Identifiable, Hashable {
    let id: Int
    let habitId: Int
    let userId: Int
    let completedDate: String
    let completedAt: String
    let quantityValue: Double?
    let note: String?
}

struct AIProgressionDTO: Codable, Hashable {
    let week: Int
    let description: String
}

struct AIPlanResponseDTO: Decodable, Hashable {
    let success: Bool
    let provider: String
    let model: String
    let habitPayload: HabitCreateRequestDTO
    let progressions: [AIProgressionDTO]
}

struct AICreateHabitResponseDTO: Decodable, Hashable {
    let success: Bool
    let provider: String
    let model: String
    let habit: BackendHabit
    let habitPayload: HabitCreateRequestDTO
    let progressions: [AIProgressionDTO]
}

struct AIPlanPreview: Identifiable, Hashable {
    let id = UUID()
    let provider: String
    let model: String
    let title: String
    let category: HabitCategory
    let description: String
    let triggerValue: String
    let frequencySummary: String
    let progressions: [AIProgressionDTO]
    let habitPayload: HabitCreateRequestDTO
}

struct AppHabitDraft: Hashable {
    let name: String
    let description: String
    let category: HabitCategory
    let kpiType: KPIType
    let scheduledDays: [Int]
    let scheduledTime: Date?
}

extension AppHabitDraft {
    func toCreateRequest() -> HabitCreateRequestDTO {
        let normalizedDays = Array(Set(scheduledDays)).sorted()
        let isDaily = normalizedDays.isEmpty || normalizedDays == Array(1...7)
        return HabitCreateRequestDTO(
            name: name,
            category: category,
            description: description,
            triggerType: "time",
            triggerValue: BackendHabitMapper.hhmmString(from: scheduledTime),
            frequencyType: isDaily ? "daily" : "custom",
            frequencyPattern: isDaily ? nil : BackendFrequencyPattern(days: normalizedDays.compactMap(BackendHabitMapper.backendDayName)),
            requiresQuantity: kpiType != .checkbox,
            quantityUnit: BackendHabitMapper.quantityUnit(for: kpiType),
            allowsNotes: true,
            motivationStatement: nil
        )
    }
}

extension HabitCreateRequestDTO {
    func toAIPlanPreview(provider: String, model: String, progressions: [AIProgressionDTO]) -> AIPlanPreview {
        AIPlanPreview(
            provider: provider,
            model: model,
            title: name,
            category: category,
            description: description,
            triggerValue: triggerValue,
            frequencySummary: BackendHabitMapper.frequencySummary(frequencyType: frequencyType, pattern: frequencyPattern),
            progressions: progressions,
            habitPayload: self
        )
    }
}

extension AIConversationMessage {
    func toDTO() -> AIConversationMessageDTO {
        AIConversationMessageDTO(role: role, content: text)
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
        AIPlanSnapshotDTO(
            habitPayload: habitPayload,
            progressions: progressions
        )
    }
}

extension BackendHabit {
    func toAppHabit(completions: [BackendCompletion] = []) -> Habit {
        Habit(
            id: String(id),
            name: name,
            category: category,
            description: description,
            kpiType: BackendHabitMapper.kpiType(requiresQuantity: requiresQuantity, quantityUnit: quantityUnit),
            scheduledDays: BackendHabitMapper.scheduledDays(frequencyType: frequencyType, pattern: frequencyPattern),
            scheduledTime: BackendHabitMapper.time(from: triggerValue),
            streak: BackendHabitMapper.streak(for: completions),
            createdAt: BackendHabitMapper.dateTime(from: createdAt) ?? Date()
        )
    }
}

extension BackendCompletion {
    func toAppHabitLog() -> HabitLog {
        HabitLog(
            id: String(id),
            habitId: String(habitId),
            date: BackendHabitMapper.dateOnly(from: completedDate) ?? Date(),
            completed: true,
            value: quantityValue,
            note: note
        )
    }
}

enum BackendHabitMapper {
    nonisolated static func kpiType(requiresQuantity: Bool, quantityUnit: String?) -> KPIType {
        guard requiresQuantity else { return .checkbox }
        if quantityUnit?.lowercased() == "minutes" {
            return .duration
        }
        return .count
    }

    nonisolated static func quantityUnit(for kpiType: KPIType) -> String? {
        switch kpiType {
        case .checkbox:
            return nil
        case .duration:
            return "minutes"
        case .count:
            return "count"
        }
    }

    nonisolated static func scheduledDays(frequencyType: String, pattern: BackendFrequencyPattern?) -> [Int] {
        if frequencyType.lowercased() == "daily" {
            return []
        }
        return (pattern?.days ?? [])
            .compactMap(weekdayNumber(for:))
            .sorted()
    }

    nonisolated static func backendDayName(for day: Int) -> String? {
        switch day {
        case 1: return "sunday"
        case 2: return "monday"
        case 3: return "tuesday"
        case 4: return "wednesday"
        case 5: return "thursday"
        case 6: return "friday"
        case 7: return "saturday"
        default: return nil
        }
    }

    nonisolated static func hhmmString(from date: Date?) -> String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "HH:mm"
        return formatter.string(from: date ?? defaultTime())
    }

    nonisolated static func time(from value: String) -> Date? {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "HH:mm"
        return formatter.date(from: value)
    }

    nonisolated static func defaultTime() -> Date {
        Calendar.current.date(from: DateComponents(hour: 7, minute: 0)) ?? Date()
    }

    nonisolated static func dateTime(from value: String?) -> Date? {
        guard let value else { return nil }
        for format in [
            "yyyy-MM-dd'T'HH:mm:ss.SSSSSS",
            "yyyy-MM-dd'T'HH:mm:ss.SSS",
            "yyyy-MM-dd'T'HH:mm:ss",
        ] {
            let formatter = DateFormatter()
            formatter.locale = Locale(identifier: "en_US_POSIX")
            formatter.timeZone = TimeZone.current
            formatter.dateFormat = format
            if let date = formatter.date(from: value) {
                return date
            }
        }
        return ISO8601DateFormatter().date(from: value)
    }

    nonisolated static func dateOnly(from value: String) -> Date? {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone.current
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.date(from: value)
    }

    nonisolated static func dateOnlyString(from date: Date) -> String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone.current
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.string(from: date)
    }

    nonisolated static func streak(for completions: [BackendCompletion], today: Date = Date()) -> Int {
        streak(for: completions.compactMap { dateOnly(from: $0.completedDate) }, today: today)
    }

    nonisolated static func streak(for completionDates: [Date], today: Date = Date()) -> Int {
        let calendar = Calendar.current
        let completionDays = Set(completionDates.map { calendar.startOfDay(for: $0) })
        let todayStart = calendar.startOfDay(for: today)

        let startDate: Date
        if completionDays.contains(todayStart) {
            startDate = todayStart
        } else if let yesterday = calendar.date(byAdding: .day, value: -1, to: todayStart), completionDays.contains(yesterday) {
            startDate = yesterday
        } else {
            return 0
        }

        var streak = 0
        var cursor: Date? = startDate
        while let day = cursor, completionDays.contains(day) {
            streak += 1
            cursor = calendar.date(byAdding: .day, value: -1, to: day)
        }
        return streak
    }

    nonisolated static func frequencySummary(frequencyType: String, pattern: BackendFrequencyPattern?) -> String {
        if frequencyType.lowercased() == "daily" {
            return "Daily"
        }

        let labels = (pattern?.days ?? []).map { $0.prefix(3).capitalized }
        if labels.isEmpty {
            return "Custom"
        }
        return labels.joined(separator: ", ")
    }

    private nonisolated static func weekdayNumber(for day: String) -> Int? {
        switch day.lowercased() {
        case "sunday": return 1
        case "monday": return 2
        case "tuesday": return 3
        case "wednesday": return 4
        case "thursday": return 5
        case "friday": return 6
        case "saturday": return 7
        default: return nil
        }
    }
}
