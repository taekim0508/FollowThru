import Foundation

struct User: Identifiable, Codable {
    var id: String
    var email: String
    var username: String
}

enum KPIType: String, Codable, CaseIterable {
    case checkbox = "Completion"
    case duration = "Duration (min)"
    case count    = "Amount"
}

struct Habit: Identifiable, Codable, Hashable {
    var id: String = UUID().uuidString
    var name: String
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

// MARK: - Community
// (Backend JSON uses snake_case; decoder uses convertFromSnakeCase)

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
