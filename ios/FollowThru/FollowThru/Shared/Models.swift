import Foundation

struct User: Identifiable, Codable {
    var id: String
    var email: String
    var username: String
}

enum HabitCategory: String, Codable, CaseIterable, Hashable {
    case fitness
    case study
    case wellness
    case reading
    case sleep

    var displayName: String {
        rawValue.capitalized
    }
}

enum KPIType: String, Codable, CaseIterable {
    case checkbox = "Completion"
    case duration = "Duration (min)"
    case count    = "Amount"
}

struct Habit: Identifiable, Codable, Hashable {
    var id: String
    var name: String
    var category: HabitCategory = .wellness
    var description: String = ""
    var kpiType: KPIType = .checkbox
    var scheduledDays: [Int] = []   // 1 = Sun … 7 = Sat
    var scheduledTime: Date? = nil
    var streak: Int = 0
    var createdAt: Date = Date()
}

struct HabitLog: Identifiable, Codable {
    var id: String = UUID().uuidString
    var habitId: String
    var date: Date
    var completed: Bool
    var value: Double? = nil        // for duration / count KPIs
    var note: String? = nil
}
