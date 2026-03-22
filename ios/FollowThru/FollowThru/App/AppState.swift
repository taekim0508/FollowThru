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

    // Community
    @Published var communityFeed: [FeedPost] = []
    @Published var friendInbox: [FriendInboxItem] = []
    @Published var friendsList: [FriendProfile] = []
    @Published var userSearchResults: [UserSearchResult] = []
    @Published var communityError: String? = nil
    @Published var isCommunityLoading: Bool = false

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
        communityFeed = []
        friendInbox = []
        friendsList = []
        userSearchResults = []
        communityError = nil
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
            if let e = error as? LocalizedError, let msg = e.errorDescription {
                communityError = msg
            } else {
                communityError = error.localizedDescription
            }
        }
        isCommunityLoading = false
    }

    func searchUsers(query: String) async {
        let q = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard q.count >= 2 else {
            userSearchResults = []
            return
        }
        communityError = nil
        do {
            userSearchResults = try await CommunityAPI.searchUsers(query: q)
        } catch {
            if let e = error as? LocalizedError, let msg = e.errorDescription {
                communityError = msg
            } else {
                communityError = error.localizedDescription
            }
        }
    }

    func sendFriendRequest(to receiverId: Int) async {
        communityError = nil
        do {
            try await CommunityAPI.sendFriendRequest(receiverId: receiverId)
            await loadCommunityData()
        } catch {
            if let e = error as? LocalizedError, let msg = e.errorDescription {
                communityError = msg
            } else {
                communityError = error.localizedDescription
            }
        }
    }

    func acceptFriendRequest(requestId: Int) async {
        communityError = nil
        do {
            try await CommunityAPI.acceptFriendRequest(requestId: requestId)
            await loadCommunityData()
        } catch {
            if let e = error as? LocalizedError, let msg = e.errorDescription {
                communityError = msg
            } else {
                communityError = error.localizedDescription
            }
        }
    }

    func declineFriendRequest(requestId: Int) async {
        communityError = nil
        do {
            try await CommunityAPI.declineFriendRequest(requestId: requestId)
            await loadCommunityData()
        } catch {
            if let e = error as? LocalizedError, let msg = e.errorDescription {
                communityError = msg
            } else {
                communityError = error.localizedDescription
            }
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
            if let e = error as? LocalizedError, let msg = e.errorDescription {
                communityError = msg
            } else {
                communityError = error.localizedDescription
            }
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
            if let e = error as? LocalizedError, let msg = e.errorDescription {
                communityError = msg
            } else {
                communityError = error.localizedDescription
            }
        }
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
