import SwiftUI

struct ProfileView: View {
    @EnvironmentObject var appState: AppState

    private let achievements = ["🔥 7 Day Streak", "✅ First Habit", "🌅 Early Bird"]

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {

                    // Avatar + name
                    VStack(spacing: 8) {
                        Image(systemName: "person.circle.fill")
                            .font(.system(size: 80))
                            .foregroundColor(Theme.softBlue)
                        Text(appState.currentUser?.username ?? "User")
                            .font(.title2).bold()
                            .foregroundColor(Theme.primary)
                        Text(appState.currentUser?.email ?? "")
                            .font(.subheadline)
                            .foregroundColor(Theme.textSecondary)
                    }
                    .padding(.top, 16)

                    // Achievements
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Achievements")
                            .font(.headline)
                            .foregroundColor(Theme.primary)
                            .padding(.horizontal)

                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 10) {
                                ForEach(achievements, id: \.self) { badge in
                                    Text(badge)
                                        .font(.subheadline).fontWeight(.medium)
                                        .padding(.horizontal, 14).padding(.vertical, 8)
                                        .background(Theme.sageLight)
                                        .foregroundColor(Theme.sage)
                                        .cornerRadius(20)
                                }
                            }
                            .padding(.horizontal)
                        }
                    }

                    // Stats row
                    HStack(spacing: 0) {
                        statCell(value: "\(appState.habits.count)", label: "Habits")
                        Divider().frame(height: 40)
                        statCell(value: "\(appState.logs.filter { $0.completed }.count)", label: "Completed")
                        Divider().frame(height: 40)
                        statCell(value: "\(maxStreak())", label: "Best Streak")
                    }
                    .padding()
                    .background(Theme.white)
                    .cornerRadius(16)
                    .shadow(color: Theme.shadow, radius: 8, x: 0, y: 2)
                    .padding(.horizontal)

                    // Settings link
                    NavigationLink(destination: SettingsView()) {
                        HStack {
                            Image(systemName: "gearshape").foregroundColor(Theme.primary)
                            Text("Settings").foregroundColor(Theme.primary)
                            Spacer()
                            Image(systemName: "chevron.right").foregroundColor(Theme.textSecondary)
                        }
                        .padding()
                        .background(Theme.white)
                        .cornerRadius(12)
                        .shadow(color: Theme.shadow, radius: 4, x: 0, y: 1)
                        .padding(.horizontal)
                    }

                    // Sign out
                    AppButton("Sign Out", variant: .secondary) {
                        appState.logout()
                    }
                    .padding(.horizontal)
                    .padding(.bottom, 24)
                }
            }
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("Profile")
            .navigationBarTitleDisplayMode(.inline)
        }
    }

    @ViewBuilder
    private func statCell(value: String, label: String) -> some View {
        VStack(spacing: 4) {
            Text(value).font(.title2).bold().foregroundColor(Theme.primary)
            Text(label).font(.caption).foregroundColor(Theme.textSecondary)
        }
        .frame(maxWidth: .infinity)
    }

    private func maxStreak() -> Int {
        appState.habits.map { $0.streak }.max() ?? 0
    }
}
