import Foundation
import SwiftUI
import Combine

@MainActor
final class AppState: ObservableObject {

    // MARK: - Auth
    @Published var isAuthenticated: Bool = false
    @Published var currentUser: User? = nil
    @Published var isAuthLoading: Bool = false
    @Published var authError: String? = nil

    // MARK: - Habits
    @Published var habits: [Habit] = []
    @Published var isHabitsLoading: Bool = false
    @Published var habitsError: String? = nil

    // MARK: - Completion Modal
    @Published var selectedHabit: Habit? = nil

    // MARK: - AI
    @Published var isAILoading: Bool = false
    @Published var aiError: String? = nil
    @Published var latestAIPlan: AIPlanPreview? = nil

    // MARK: - Community
    @Published var communityFeed: [FeedPost] = []
    @Published var friendInbox: [FriendInboxItem] = []
    @Published var friendsList: [FriendProfile] = []
    @Published var userSearchResults: [UserSearchResult] = []
    @Published var communityError: String? = nil
    @Published var isCommunityLoading: Bool = false

    // MARK: - Date Helpers

    private var todayString: String {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        return f.string(from: Date())
    }

    // MARK: - Auth

    func register(email: String, password: String, username: String) async {
        isAuthLoading = true
        authError = nil
        do {
            let (user, token) = try await AuthAPI.register(
                email: email, password: password, name: username
            )
            TokenStore.save(token)
            currentUser = user
            isAuthenticated = true
            await checkStreaksAndLoadHabits()
        } catch {
            authError = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
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
            await checkStreaksAndLoadHabits()
        } catch {
            authError = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        }
        isAuthLoading = false
    }

    func restoreSessionIfNeeded() async {
        guard TokenStore.hasToken, !isAuthenticated else { return }
        isAuthLoading = true
        do {
            let user = try await AuthAPI.getMe()
            currentUser = user
            isAuthenticated = true
            await checkStreaksAndLoadHabits()
        } catch {
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
        selectedHabit = nil
        communityFeed = []
        friendInbox = []
        friendsList = []
        userSearchResults = []
        communityError = nil
        habitsError = nil
        aiError = nil
        latestAIPlan = nil
    }

    func updateAccount(
        name: String? = nil,
        email: String? = nil,
        currentPassword: String? = nil,
        newPassword: String? = nil
    ) async {
        isAuthLoading = true
        authError = nil
        do {
            let user = try await AuthAPI.updateMe(
                name: name,
                email: email,
                currentPassword: currentPassword,
                newPassword: newPassword
            )
            currentUser = user
        } catch {
            authError = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        }
        isAuthLoading = false
    }

    // MARK: - Habits

    func loadHabits() async {
        guard isAuthenticated else { return }
        isHabitsLoading = true
        habitsError = nil
        do {
            habits = try await HabitsAPI.listHabits()
        } catch {
            habitsError = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        }
        isHabitsLoading = false
    }

    /// Called once per day on app launch.
    /// Resets broken streaks then returns updated habit list in one call.
    /// Falls back to regular loadHabits if check-streaks fails.
    func checkStreaksAndLoadHabits() async {
        guard isAuthenticated else { return }

        // only call check-streaks once per calendar day
        let today = todayString
        let lastChecked = UserDefaults.standard.string(forKey: "lastStreakCheckDate")

        if lastChecked == today {
            // already checked today — just load habits normally
            await loadHabits()
            return
        }

        isHabitsLoading = true
        habitsError = nil
        do {
            habits = try await HabitsAPI.checkStreaks()
            UserDefaults.standard.set(today, forKey: "lastStreakCheckDate")
        } catch {
            // fallback to regular load if check-streaks fails
            await loadHabits()
        }
        isHabitsLoading = false
    }

    func createHabit(
        name: String,
        description: String,
        category: String,
        habitType: String,
        targetValue: Double?,
        quantityUnit: String?,
        triggerValue: String?,  // changed to Optional
        frequencyPattern: [String: [String]],
        motivationStatement: String? = nil
    ) async {
        habitsError = nil
        do {
            _ = try await HabitsAPI.createHabit(
                name: name,
                description: description,
                category: category,
                habitType: habitType,
                targetValue: targetValue,
                quantityUnit: quantityUnit,
                triggerValue: triggerValue,
                frequencyPattern: frequencyPattern,
                motivationStatement: motivationStatement
            )
            await loadHabits()
        } catch {
            habitsError = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        }
    }

    func updateHabit(
        _ habit: Habit,
        name: String? = nil,
        description: String? = nil,
        triggerValue: Nullable<String>? = nil,  // changed
        frequencyPattern: [String: [String]]? = nil,
        habitType: String? = nil,
        targetValue: Double? = nil,
        quantityUnit: String? = nil,
        status: String? = nil,
        category: String? = nil,
        motivationStatement: String? = nil
    ) async {
        habitsError = nil
        do {
            _ = try await HabitsAPI.updateHabit(
                id: habit.id,
                name: name,
                description: description,
                triggerValue: triggerValue,
                frequencyPattern: frequencyPattern,
                habitType: habitType,
                targetValue: targetValue,
                quantityUnit: quantityUnit,
                status: status,
                category: category,
                motivationStatement: motivationStatement
            )
            await loadHabits()
        } catch {
            habitsError = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        }
    }

    func deleteHabit(_ habit: Habit) async {
        habitsError = nil
        do {
            try await HabitsAPI.deleteHabit(id: habit.id)
            habits.removeAll { $0.id == habit.id }
        } catch {
            habitsError = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        }
    }

    // MARK: - Completions

    /// Complete a binary habit or create the first log for a tracked habit.
    func completeHabit(_ habit: Habit, note: String? = nil) async {
        habitsError = nil
        do {
            let result = try await HabitsAPI.completeHabit(
                habitId: habit.id,
                completedDate: todayString,
                note: note
            )
            updateHabitStreakLocally(habitId: habit.id, result: result)
            await loadHabits()
        } catch {
            habitsError = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        }
    }

    /// Log a progress value for a tracked habit.
    /// Uses POST if no log exists today, PATCH if one already exists.
    func logProgress(_ habit: Habit, progressValue: Double, note: String? = nil) async {
        habitsError = nil
        do {
            let result: CompletionResponse
            if habit.todayProgress == nil {
                // no log yet today — create it
                result = try await HabitsAPI.completeHabit(
                    habitId: habit.id,
                    completedDate: todayString,
                    progressValue: progressValue,
                    note: note
                )
            } else {
                // log exists — update it
                result = try await HabitsAPI.updateProgress(
                    habitId: habit.id,
                    completedDate: todayString,
                    progressValue: progressValue,
                    note: note
                )
            }
            updateHabitStreakLocally(habitId: habit.id, result: result)
            await loadHabits()
        } catch {
            habitsError = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        }
    }

    /// Update streak fields locally so UI reflects changes immediately
    /// without waiting for the next full loadHabits() call.
    private func updateHabitStreakLocally(habitId: Int, result: CompletionResponse) {
        if let idx = habits.firstIndex(where: { $0.id == habitId }) {
            habits[idx].currentStreak = result.currentStreak
            habits[idx].maxStreak = result.maxStreak
            habits[idx].todayComplete = result.isComplete
            habits[idx].todayProgress = result.progressValue
        }
    }

    // MARK: - Habit Helpers

    /// Habits scheduled for today's weekday
    var todaysHabits: [Habit] {
        let formatter = DateFormatter()
        formatter.dateFormat = "EEEE"
        let todayName = formatter.string(from: Date()).lowercased()
        return habits.filter { $0.frequencyPattern.days.contains(todayName) }
    }

    /// Habits NOT scheduled for today
    var nonTodayHabits: [Habit] {
        let formatter = DateFormatter()
        formatter.dateFormat = "EEEE"
        let todayName = formatter.string(from: Date()).lowercased()
        return habits.filter { !$0.frequencyPattern.days.contains(todayName) }
    }

    // MARK: - Community

    func loadCommunityData() async {
        guard isAuthenticated else { return }
        isCommunityLoading = true
        communityError = nil
        do {
            async let feed = CommunityAPI.feed(limit: 40)
            async let inbox = CommunityAPI.inboxDetail()
            async let friends = CommunityAPI.friendsDetail()
            communityFeed = try await feed
            friendInbox = try await inbox
            friendsList = try await friends
        } catch {
            communityError = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        }
        isCommunityLoading = false
    }

    func searchUsers(query: String) async {
        let q = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard q.count >= 2 else { userSearchResults = []; return }
        communityError = nil
        do {
            userSearchResults = try await CommunityAPI.searchUsers(query: q)
        } catch {
            communityError = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        }
    }

    func sendFriendRequest(to receiverId: Int) async {
        communityError = nil
        do {
            try await CommunityAPI.sendFriendRequest(receiverId: receiverId)
            await loadCommunityData()
        } catch {
            communityError = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        }
    }

    func acceptFriendRequest(requestId: Int) async {
        communityError = nil
        do {
            try await CommunityAPI.acceptFriendRequest(requestId: requestId)
            await loadCommunityData()
        } catch {
            communityError = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        }
    }

    func declineFriendRequest(requestId: Int) async {
        communityError = nil
        do {
            try await CommunityAPI.declineFriendRequest(requestId: requestId)
            await loadCommunityData()
        } catch {
            communityError = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        }
    }

    func toggleLike(for post: FeedPost) async {
        communityError = nil
        do {
            if post.viewerHasLiked {
                try await CommunityAPI.unlikePost(postId: post.id)
            } else {
                try await CommunityAPI.likePost(postId: post.id)
            }
            communityFeed = try await CommunityAPI.feed(limit: 40)
        } catch {
            communityError = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        }
    }

    func addComment(postId: Int, text: String) async {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        communityError = nil
        do {
            _ = try await CommunityAPI.addComment(postId: postId, text: trimmed)
            communityFeed = try await CommunityAPI.feed(limit: 40)
        } catch {
            communityError = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        }
    }

    // MARK: - AI

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
    func createHabitFromAI(draft: AIIntakeDraftDTO) async -> AICreatedHabitDTO? {
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
            await loadHabits()
            return response.habit
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

    private func errorMessage(from error: Error) -> String {
        if let localized = error as? LocalizedError, let message = localized.errorDescription {
            return message
        }
        return error.localizedDescription
    }
}
