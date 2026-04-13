import Foundation

// MARK: - Achievement rules (product preference)
//
// Badges are derived only from habit data already synced from the API (no fake “always unlocked” list).
//
// 1. **First habit** — User has created at least one habit (`habits.count >= 1`).
//    Encourages getting started with the core loop.
//
// 2. **7+ day streak** — Best lifetime streak across all habits is at least 7 days (`max(maxStreak) >= 7`).
//    Uses server-maintained `maxStreak` (consecutive scheduled completions), not calendar luck.
//
// 3. **All habits done today** — Non-empty habit list and every habit has `todayComplete == true`.
//    Rewards a full daily win when the user clears every active habit for the current day.
//
// Locked badges stay visible but dimmed so progress feels attainable.

struct AchievementBadge: Identifiable, Equatable {
    let id: String
    let title: String
    let isUnlocked: Bool
}

enum AchievementRules {
    static func badges(for habits: [Habit]) -> [AchievementBadge] {
        let bestStreak = habits.map(\.maxStreak).max() ?? 0
        let allDoneToday = !habits.isEmpty && habits.allSatisfy(\.todayComplete)

        return [
            AchievementBadge(
                id: "first_habit",
                title: "✅ First habit",
                isUnlocked: !habits.isEmpty
            ),
            AchievementBadge(
                id: "streak_7",
                title: "🔥 7+ day streak",
                isUnlocked: bestStreak >= 7
            ),
            AchievementBadge(
                id: "all_today",
                title: "🌟 All habits done today",
                isUnlocked: allDoneToday
            ),
        ]
    }
}
