import SwiftUI

struct CommunityView: View {
    @EnvironmentObject var appState: AppState
    @State private var searchText = ""
    @State private var commentPost: FeedPost?
    @State private var newComment = ""

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    if let err = appState.communityError {
                        Text(err)
                            .font(.footnote)
                            .foregroundColor(.red)
                            .padding(.horizontal)
                    }

                    // Search
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Find people")
                            .font(.headline)
                            .foregroundColor(Theme.primary)
                        HStack {
                            TextField("Search by name or email", text: $searchText)
                                .foregroundColor(Theme.primary)
                                .accentColor(Theme.primary)
                                .textInputAutocapitalization(.never)
                                .keyboardType(.emailAddress)
                                .padding(10)
                                .background(Theme.white)
                                .cornerRadius(10)
                                .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.lightGray))
                            Button("Search") {
                                Task { await appState.searchUsers(query: searchText) }
                            }
                            .disabled(searchText.trimmingCharacters(in: .whitespaces).count < 2)
                        }
                        ForEach(appState.userSearchResults) { u in
                            searchRow(u)
                        }
                    }
                    .padding(.horizontal)

                    // Inbox
                    if !appState.friendInbox.isEmpty {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Friend requests")
                                .font(.headline)
                                .foregroundColor(Theme.primary)
                            ForEach(appState.friendInbox) { req in
                                inboxRow(req)
                            }
                        }
                        .padding(.horizontal)
                    }

                    // Friends
                    if !appState.friendsList.isEmpty {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Your friends")
                                .font(.headline)
                                .foregroundColor(Theme.primary)
                            ForEach(appState.friendsList) { f in
                                HStack {
                                    Image(systemName: "person.circle.fill")
                                        .foregroundColor(Theme.sage)
                                    Text(f.name ?? f.email)
                                        .foregroundColor(Theme.primary)
                                    Spacer()
                                }
                                .padding(.vertical, 4)
                            }
                        }
                        .padding(.horizontal)
                    }

                    // Feed
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Activity")
                            .font(.headline)
                            .foregroundColor(Theme.primary)
                        if appState.communityFeed.isEmpty && !appState.isCommunityLoading {
                            Text("No posts yet. Complete a habit (or add friends) to see activity here.")
                                .font(.subheadline)
                                .foregroundColor(Theme.textSecondary)
                        }
                        ForEach(appState.communityFeed) { post in
                            postCard(post)
                        }
                    }
                    .padding(.horizontal)
                    .padding(.bottom, 24)
                }
            }
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("Community")
            .navigationBarTitleDisplayMode(.inline)
            .refreshable {
                await appState.loadCommunityData()
            }
            .task {
                await appState.loadCommunityData()
            }
            .sheet(item: $commentPost, onDismiss: { newComment = "" }) { post in
                CommentSheet(post: post, newComment: $newComment)
                    .environmentObject(appState)
            }
        }
    }

    @ViewBuilder
    private func searchRow(_ u: UserSearchResult) -> some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(u.name ?? u.email)
                    .font(.subheadline).fontWeight(.semibold)
                    .foregroundColor(Theme.primary)
                Text(u.email)
                    .font(.caption)
                    .foregroundColor(Theme.textSecondary)
            }
            Spacer()
            relationshipButton(for: u)
        }
        .padding(12)
        .background(Theme.white)
        .cornerRadius(12)
        .shadow(color: Theme.shadow, radius: 4, x: 0, y: 1)
    }

    @ViewBuilder
    private func relationshipButton(for u: UserSearchResult) -> some View {
        switch u.relationship {
        case "friends":
            Text("Friends")
                .font(.caption).fontWeight(.semibold)
                .foregroundColor(Theme.textSecondary)
        case "pending_sent":
            Text("Pending")
                .font(.caption).fontWeight(.semibold)
                .foregroundColor(Theme.textSecondary)
        case "pending_received":
            Text("Incoming")
                .font(.caption).fontWeight(.semibold)
                .foregroundColor(Theme.sage)
        default:
            Button("Add") {
                Task {
                    await appState.sendFriendRequest(to: u.id)
                    await appState.searchUsers(query: searchText)
                }
            }
            .font(.caption).fontWeight(.semibold)
            .padding(.horizontal, 12).padding(.vertical, 6)
            .background(Theme.primary)
            .foregroundColor(.white)
            .cornerRadius(8)
        }
    }

    private func inboxRow(_ req: FriendInboxItem) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(req.requesterName ?? req.requesterEmail)
                .font(.subheadline).fontWeight(.semibold)
                .foregroundColor(Theme.primary)
            HStack {
                Button("Accept") {
                    Task { await appState.acceptFriendRequest(requestId: req.id) }
                }
                .buttonStyle(.borderedProminent)
                .tint(Theme.primary)
                Button("Decline") {
                    Task { await appState.declineFriendRequest(requestId: req.id) }
                }
                .buttonStyle(.bordered)
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.white)
        .cornerRadius(12)
        .shadow(color: Theme.shadow, radius: 4, x: 0, y: 1)
    }

    private func postCard(_ post: FeedPost) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(post.authorName ?? post.authorEmail)
                .font(.caption)
                .foregroundColor(Theme.textSecondary)
            Text(post.title)
                .font(.headline)
                .foregroundColor(Theme.primary)
            Text(post.body)
                .font(.subheadline)
                .foregroundColor(Theme.primary)
            HStack(spacing: 16) {
                Button {
                    Task { await appState.toggleLike(for: post) }
                } label: {
                    Label("\(post.likeCount)", systemImage: post.viewerHasLiked ? "heart.fill" : "heart")
                }
                .foregroundColor(post.viewerHasLiked ? .red : Theme.primary)

                Button {
                    commentPost = post
                } label: {
                    Label("\(post.commentCount)", systemImage: "bubble.left")
                }
                .foregroundColor(Theme.primary)
            }
            .font(.subheadline)
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.white)
        .cornerRadius(14)
        .shadow(color: Theme.shadow, radius: 6, x: 0, y: 2)
    }
}

private struct CommentSheet: View {
    @EnvironmentObject var appState: AppState
    @Environment(\.dismiss) private var dismiss
    let post: FeedPost
    @Binding var newComment: String

    @State private var comments: [CommentItem] = []
    @State private var loading = true

    var body: some View {
        NavigationStack {
            VStack {
                if loading {
                    ProgressView()
                } else {
                    List(comments) { c in
                        VStack(alignment: .leading, spacing: 4) {
                            Text(c.authorName ?? c.authorEmail)
                                .font(.caption)
                                .foregroundColor(Theme.textSecondary)
                            Text(c.body)
                                .font(.body)
                        }
                    }
                }
                HStack {
                    TextField("Comment", text: $newComment)
                        .foregroundColor(Theme.primary)
                        .accentColor(Theme.primary)
                        .padding(10)
                        .background(Theme.white)
                        .cornerRadius(10)
                        .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.lightGray))
                    Button("Send") {
                        Task {
                            let t = newComment.trimmingCharacters(in: .whitespacesAndNewlines)
                            guard !t.isEmpty else { return }
                            await appState.addComment(postId: post.id, text: t)
                            newComment = ""
                            do {
                                comments = try await CommunityAPI.comments(postId: post.id)
                            } catch {
                                comments = []
                            }
                            dismiss()
                        }
                    }
                    .disabled(newComment.trimmingCharacters(in: .whitespaces).isEmpty)
                }
                .padding()
            }
            .navigationTitle("Comments")
            .navigationBarTitleDisplayMode(.inline)
            .task {
                loading = true
                do {
                    comments = try await CommunityAPI.comments(postId: post.id)
                } catch {
                    comments = []
                }
                loading = false
            }
        }
    }
}
