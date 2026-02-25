import Foundation
import SwiftUI
import Combine

@MainActor
final class AppState: ObservableObject {
    @Published var isAuthenticated: Bool = false
    @Published var currentUser: User? = nil
    @Published var habits: [Habit] = []
    @Published var logs: [HabitLog] = []
    @Published var selectedHabit: Habit? = nil
    @Published var showCompletionModal: Bool = false

    // Auth state
    @Published var isAuthLoading: Bool = false
    @Published var authError: String? = nil

    // MARK: - Auth

    func register(email: String, password: String, username: String) async {
        isAuthLoading = true
        authError = nil

        do {
            let (user, token) = try await AuthAPI.register(email: email, password: password, name: username)
            TokenStore.save(token)
            currentUser = user
            isAuthenticated = true
        } catch {
            if let err = error as? LocalizedError, let msg = err.errorDescription {
                authError = msg
            } else {
                authError = error.localizedDescription
            }
        }

        isAuthLoading = false
    }

    func login(email: String, password: String) async {
        isAuthLoading = true
        authError = nil

        do {
            let (user, token) = try await AuthAPI.login(email: email, password: password)
            TokenStore.save(token)
            currentUser = user
            isAuthenticated = true
        } catch {
            if let err = error as? LocalizedError, let msg = err.errorDescription {
                authError = msg
            } else {
                authError = error.localizedDescription
            }
        }

        isAuthLoading = false
    }

    func restoreSessionIfNeeded() async {
        guard TokenStore.hasToken, !isAuthenticated else { return }

        isAuthLoading = true
        authError = nil

        do {
            let user = try await AuthAPI.getMe()
            currentUser = user
            isAuthenticated = true
        } catch {
            // If token is invalid/expired, clear it and stay logged out.
            TokenStore.clear()
            isAuthenticated = false
            currentUser = nil
        }

        isAuthLoading = false
    }

    func logout() {
        TokenStore.clear()
        isAuthenticated = false
        currentUser = nil
        habits = []
        logs = []
        selectedHabit = nil
    }

    /// Update profile (name, email, password). Pass only fields that changed; use nil to skip.
    func updateAccount(name: String? = nil, email: String? = nil, currentPassword: String? = nil, newPassword: String? = nil) async {
        isAuthLoading = true
        authError = nil

        do {
            let user = try await AuthAPI.updateMe(name: name, email: email, currentPassword: currentPassword, newPassword: newPassword)
            currentUser = user
        } catch {
            if let err = error as? LocalizedError, let msg = err.errorDescription {
                authError = msg
            } else {
                authError = error.localizedDescription
            }
        }

        isAuthLoading = false
    }

    // MARK: - Habits & logs

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

    func markComplete(habit: Habit, value: Double? = nil, note: String? = nil, completed: Bool = true) {
        let log = HabitLog(
            habitId: habit.id,
            date: Date(),
            completed: completed,
            value: value,
            note: note
        )
        logs.append(log)
        if completed, let idx = habits.firstIndex(where: { $0.id == habit.id }) {
            habits[idx].streak += 1
        }
    }
    
    func deleteHabit(_ habit: Habit) {
        habits.removeAll { $0.id == habit.id }
        logs.removeAll { $0.habitId == habit.id }
    }
    
    func updateHabit(_ habit: Habit, name: String, description: String, kpiType: KPIType, kpiTarget: Double?, scheduledDays: [Int], scheduledTime: Date?) {
        guard let idx = habits.firstIndex(where: { $0.id == habit.id }) else { return }
        habits[idx].name = name
        habits[idx].description = description
        habits[idx].kpiType = kpiType
        habits[idx].kpiTarget = kpiTarget
        habits[idx].scheduledDays = scheduledDays
        habits[idx].scheduledTime = scheduledTime
    }
}
