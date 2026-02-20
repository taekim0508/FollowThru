import Foundation
import SwiftUI
import Combine

final class AppState: ObservableObject {
    @Published var isAuthenticated: Bool = false
    @Published var currentUser: User? = nil
    @Published var habits: [Habit] = []
    @Published var logs: [HabitLog] = []
    @Published var selectedHabit: Habit? = nil
    @Published var showCompletionModal: Bool = false

    func logout() {
        isAuthenticated = false
        currentUser = nil
        habits = []
        logs = []
        selectedHabit = nil
    }

    func logsFor(habit: Habit, in month: Date) -> [HabitLog] {
        let cal = Calendar.current
        return logs.filter {
            $0.habitId == habit.id &&
            cal.isDate($0.date, equalTo: month, toGranularity: .month)
        }
    }

    func isCompleted(habit: Habit, on date: Date = Date()) -> Bool {
        let cal = Calendar.current
        return logs.contains {
            $0.habitId == habit.id &&
            $0.completed &&
            cal.isDate($0.date, inSameDayAs: date)
        }
    }

    func markComplete(habit: Habit, note: String? = nil) {
        let log = HabitLog(
            habitId: habit.id,
            date: Date(),
            completed: true,
            note: note
        )
        logs.append(log)
        if let idx = habits.firstIndex(where: { $0.id == habit.id }) {
            habits[idx].streak += 1
        }
    }
}
