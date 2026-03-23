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
    @Published var isHabitsLoading: Bool = false
    @Published var habitsError: String? = nil
    @Published var isAILoading: Bool = false
    @Published var aiError: String? = nil
    @Published var latestAIPlan: AIPlanPreview? = nil

    // MARK: - Auth

    func register(email: String, password: String, username: String) async {
        isAuthLoading = true
        authError = nil
        defer { isAuthLoading = false }

        do {
            let (user, token) = try await AuthAPI.register(email: email, password: password, name: username)
            TokenStore.save(token)
            currentUser = user
            isAuthenticated = true
            _ = await refreshHabits()
        } catch {
            if let err = error as? LocalizedError, let msg = err.errorDescription {
                authError = msg
            } else {
                authError = error.localizedDescription
            }
        }
    }

    func login(email: String, password: String) async {
        isAuthLoading = true
        authError = nil
        defer { isAuthLoading = false }

        do {
            let (user, token) = try await AuthAPI.login(email: email, password: password)
            TokenStore.save(token)
            currentUser = user
            isAuthenticated = true
            _ = await refreshHabits()
        } catch {
            if let err = error as? LocalizedError, let msg = err.errorDescription {
                authError = msg
            } else {
                authError = error.localizedDescription
            }
        }
    }

    func restoreSessionIfNeeded() async {
        guard TokenStore.hasToken, !isAuthenticated else { return }

        isAuthLoading = true
        authError = nil
        defer { isAuthLoading = false }

        do {
            let user = try await AuthAPI.getMe()
            currentUser = user
            isAuthenticated = true
            _ = await refreshHabits()
        } catch {
            // If token is invalid/expired, clear it and stay logged out.
            TokenStore.clear()
            isAuthenticated = false
            currentUser = nil
        }
    }

    func logout() {
        TokenStore.clear()
        isAuthenticated = false
        currentUser = nil
        habits = []
        logs = []
        selectedHabit = nil
        habitsError = nil
        aiError = nil
        latestAIPlan = nil
    }

    /// Update profile (name, email, password). Pass only fields that changed; use nil to skip.
    func updateAccount(name: String? = nil, email: String? = nil, currentPassword: String? = nil, newPassword: String? = nil) async {
        isAuthLoading = true
        authError = nil
        defer { isAuthLoading = false }

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
    }

    // MARK: - Habits & logs

    @discardableResult
    func refreshHabits() async -> Bool {
        guard isAuthenticated else {
            habits = []
            logs = []
            selectedHabit = nil
            return false
        }

        isHabitsLoading = true
        habitsError = nil
        defer { isHabitsLoading = false }

        do {
            let backendHabits = try await HabitsAPI.listHabits()
            let completionMap = Dictionary(uniqueKeysWithValues: try await loadCompletions(for: backendHabits))

            let refreshedHabits = backendHabits.map { backendHabit in
                backendHabit.toAppHabit(completions: completionMap[backendHabit.id] ?? [])
            }
            let refreshedLogs = completionMap.values.flatMap { $0 }.map { $0.toAppHabitLog() }

            habits = refreshedHabits.sorted { $0.createdAt < $1.createdAt }
            logs = refreshedLogs.sorted { $0.date > $1.date }
            selectedHabit = refreshedSelection(from: refreshedHabits)
            return true
        } catch {
            habitsError = errorMessage(from: error)
            return false
        }
    }

    @discardableResult
    func createHabit(_ draft: AppHabitDraft) async -> Habit? {
        habitsError = nil

        do {
            let appHabit = try await HabitsAPI.createHabit(draft.toCreateRequest()).toAppHabit()
            upsertHabit(appHabit)
            return appHabit
        } catch {
            habitsError = errorMessage(from: error)
            return nil
        }
    }

    @discardableResult
    func requestAIPlan(
        goal: String,
        category: HabitCategory,
        context: AIRequestContext? = nil
    ) async -> AIPlanPreview? {
        isAILoading = true
        aiError = nil
        defer { isAILoading = false }

        do {
            let response = try await AIAPI.generatePlan(
                AIGenerateRequestDTO(
                    userGoal: goal,
                    category: category,
                    context: context
                )
            )
            let preview = response.habitPayload.toAIPlanPreview(
                provider: response.provider,
                model: response.model,
                progressions: response.progressions
            )
            latestAIPlan = preview
            return preview
        } catch {
            aiError = errorMessage(from: error)
            return nil
        }
    }

    @discardableResult
    func submitAIIntake(
        recentMessages: [AIConversationMessage],
        currentDraft: AIIntakeDraftDTO,
        latestUserMessage: String
    ) async -> AIIntakeResponseDTO? {
        isAILoading = true
        aiError = nil
        defer { isAILoading = false }

        do {
            return try await AIAPI.intake(
                AIIntakeRequestDTO(
                    recentMessages: recentMessages.map { $0.toDTO() },
                    currentDraft: currentDraft,
                    latestUserMessage: latestUserMessage
                )
            )
        } catch {
            aiError = errorMessage(from: error)
            return nil
        }
    }

    @discardableResult
    func requestAIPlan(from draft: AIIntakeDraftDTO) async -> AIPlanPreview? {
        isAILoading = true
        aiError = nil
        defer { isAILoading = false }

        do {
            let response = try await AIAPI.generatePlan(from: draft)
            let preview = response.habitPayload.toAIPlanPreview(
                provider: response.provider,
                model: response.model,
                progressions: response.progressions
            )
            latestAIPlan = preview
            return preview
        } catch {
            aiError = errorMessage(from: error)
            return nil
        }
    }

    @discardableResult
    func createHabitFromAI(
        goal: String,
        category: HabitCategory,
        context: AIRequestContext? = nil
    ) async -> Habit? {
        isAILoading = true
        aiError = nil
        defer { isAILoading = false }

        do {
            let response = try await AIAPI.generateAndCreate(
                AIGenerateRequestDTO(
                    userGoal: goal,
                    category: category,
                    context: context
                )
            )
            latestAIPlan = response.habitPayload.toAIPlanPreview(
                provider: response.provider,
                model: response.model,
                progressions: response.progressions
            )
            let appHabit = response.habit.toAppHabit()
            upsertHabit(appHabit)
            return appHabit
        } catch {
            aiError = errorMessage(from: error)
            return nil
        }
    }

    @discardableResult
    func createHabitFromAI(draft: AIIntakeDraftDTO) async -> Habit? {
        isAILoading = true
        aiError = nil
        defer { isAILoading = false }

        do {
            let response = try await AIAPI.generateAndCreate(from: draft)
            latestAIPlan = response.habitPayload.toAIPlanPreview(
                provider: response.provider,
                model: response.model,
                progressions: response.progressions
            )
            let appHabit = response.habit.toAppHabit()
            upsertHabit(appHabit)
            return appHabit
        } catch {
            aiError = errorMessage(from: error)
            return nil
        }
    }

    @discardableResult
    func reviseAIPlan(
        draft: AIIntakeDraftDTO,
        currentPlan: AIPlanPreview,
        critique: String,
        recentMessages: [AIConversationMessage]
    ) async -> AIRevisePlanResponseDTO? {
        isAILoading = true
        aiError = nil
        defer { isAILoading = false }

        do {
            let response = try await AIAPI.revisePlan(
                AIRevisePlanRequestDTO(
                    draft: draft,
                    currentPlan: currentPlan.toSnapshotDTO(),
                    critique: critique,
                    recentMessages: recentMessages.map { $0.toDTO() }
                )
            )
            if let planTweak = response.planTweak {
                latestAIPlan = planTweak.toAIPlanPreview()
            }
            return response
        } catch {
            aiError = errorMessage(from: error)
            return nil
        }
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

    @discardableResult
    func markComplete(habit: Habit, note: String? = nil, on date: Date = Date()) async -> Bool {
        habitsError = nil

        guard let habitID = Int(habit.id) else {
            habitsError = "Habit is unavailable"
            return false
        }

        do {
            let completion = try await CompletionsAPI.completeHabit(
                habitID: habitID,
                completedDate: BackendHabitMapper.dateOnlyString(from: date),
                note: note
            )
            applyCompletion(completion.toAppHabitLog())
            return true
        } catch {
            habitsError = errorMessage(from: error)
            return false
        }
    }

    private func loadCompletions(for backendHabits: [BackendHabit]) async throws -> [(Int, [BackendCompletion])] {
        try await withThrowingTaskGroup(of: (Int, [BackendCompletion]).self) { group in
            for habit in backendHabits {
                group.addTask {
                    let completions = try await CompletionsAPI.listCompletions(habitID: habit.id)
                    return (habit.id, completions)
                }
            }

            var pairs: [(Int, [BackendCompletion])] = []
            for try await pair in group {
                pairs.append(pair)
            }
            return pairs
        }
    }

    private func refreshedSelection(from habits: [Habit]) -> Habit? {
        guard let selectedHabit else { return habits.first }
        return habits.first { $0.id == selectedHabit.id } ?? habits.first
    }

    private func upsertHabit(_ habit: Habit) {
        if let index = habits.firstIndex(where: { $0.id == habit.id }) {
            habits[index] = habit
        } else {
            habits.append(habit)
            habits.sort { $0.createdAt < $1.createdAt }
        }
    }

    private func applyCompletion(_ log: HabitLog) {
        logs.removeAll { existingLog in
            existingLog.habitId == log.habitId && Calendar.current.isDate(existingLog.date, inSameDayAs: log.date)
        }
        logs.append(log)
        logs.sort { $0.date > $1.date }

        if let index = habits.firstIndex(where: { $0.id == log.habitId }) {
            let completionDates = logs
                .filter { $0.habitId == log.habitId && $0.completed }
                .map(\.date)
            habits[index].streak = BackendHabitMapper.streak(for: completionDates)
        }
    }

    private func errorMessage(from error: Error) -> String {
        if let localized = error as? LocalizedError, let message = localized.errorDescription {
            return message
        }
        return error.localizedDescription
    }
}
