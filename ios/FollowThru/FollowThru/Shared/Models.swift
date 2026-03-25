import Foundation

// MARK: - User
struct User: Identifiable, Codable {
    var id: String
    var email: String
    var username: String
}

// MARK: - Habit
struct Habit: Identifiable, Codable, Hashable {
    // MARK: Core
    let id: Int
    var name: String
    var description: String
    var category: String
    // "active" | "paused" | "archived"
    var status: String

    // MARK: Habit Type
    // "binary"  = checkbox, just did it or not
    // "tracked" = numeric target, user logs a value toward a goal
    var habitType: String

    // numeric goal for tracked habits (e.g. 30 for "30 minutes", 10 for "10 pages")
    // null for binary habits
    var targetValue: Double?

    // display label for the numeric value (e.g. "minutes", "pages", "reps")
    // null for binary habits
    var quantityUnit: String?

    // MARK: Scheduling
    // "time" = time-based trigger | "location" = geofence-based (future)
    var triggerType: String

    // for time-based triggers: "HH:MM" format (e.g. "07:00")
    var triggerValue: String

    // scheduled days — {"days": ["monday", "tuesday"...]}
    // always present. all 7 days = every day.
    var frequencyPattern: FrequencyPattern

    // MARK: Today's Progress
    // current logged value for today (nil if not logged yet)
    var todayProgress: Double?

    // same as targetValue — included for convenience
    var todayTarget: Double?

    // whether today's habit is fully complete
    var todayComplete: Bool

    // MARK: Streak
    // consecutive scheduled days completed (respects schedule, has grace period)
    var currentStreak: Int

    // lifetime best streak — never resets
    var maxStreak: Int

    // last date a completion was counted toward streak
    var streakLastUpdated: String?

    // MARK: Timestamps
    var createdAt: String?
    var updatedAt: String?
}

// MARK: - FrequencyPattern
// mirrors backend {"days": ["monday", "tuesday"...]}
struct FrequencyPattern: Codable, Hashable {
    var days: [String]

    // convenience — check if a given weekday name is scheduled
    // weekday name should be lowercase e.g. "monday"
    func includes(_ weekdayName: String) -> Bool {
        days.contains(weekdayName.lowercased())
    }

    // convenience — check if a given Date is a scheduled day
    func includesDate(_ date: Date) -> Bool {
        let formatter = DateFormatter()
        formatter.dateFormat = "EEEE"  // full weekday name e.g. "Monday"
        let name = formatter.string(from: date).lowercased()
        return days.contains(name)
    }

    // all 7 days selected — treat as every day
    var isEveryDay: Bool {
        days.count == 7
    }
}

// MARK: - HabitLog
// local representation of a completion record from the backend
struct HabitLog: Identifiable, Codable {
    var id: Int
    var habitId: Int
    var completedDate: String    // "YYYY-MM-DD"
    var progressValue: Double?
    var isComplete: Bool
    var note: String?
}

// MARK: - Completion response from POST /complete or PATCH /progress
struct CompletionResponse: Codable {
    let id: Int
    let habitId: Int
    let userId: Int
    let completedDate: String
    let progressValue: Double?
    let isComplete: Bool
    let note: String?
    let currentStreak: Int
    let maxStreak: Int
}

// MARK: - Community
// (backend JSON uses snake_case — decoder uses convertFromSnakeCase)

struct UserSearchResult: Codable, Identifiable {
    let id: Int
    let email: String
    let name: String?
    let relationship: String
}

struct FriendInboxItem: Codable, Identifiable {
    let id: Int
    let requesterId: Int
    let requesterName: String?
    let requesterEmail: String
    let message: String?
    let createdAt: String
}

struct FriendProfile: Codable, Identifiable {
    let id: Int
    let email: String
    let name: String?
}

struct FeedPost: Codable, Identifiable {
    let id: Int
    let authorId: Int
    let authorName: String?
    let authorEmail: String
    let postType: String
    let title: String
    let body: String
    let habitId: Int?
    let createdAt: String
    let likeCount: Int
    let commentCount: Int
    let viewerHasLiked: Bool
}

struct CommentItem: Codable, Identifiable {
    let id: Int
    let userId: Int
    let authorName: String?
    let authorEmail: String
    let body: String
    let createdAt: String
}

extension FeedPost: Hashable {
    static func == (lhs: FeedPost, rhs: FeedPost) -> Bool { lhs.id == rhs.id }
    func hash(into hasher: inout Hasher) { hasher.combine(id) }
}
