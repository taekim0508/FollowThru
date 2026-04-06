import SwiftUI

struct ProfileView: View {
    @EnvironmentObject var appState: AppState

    private let achievements = ["🔥 7 Day Streak", "✅ First Habit", "🌅 Early Bird"]

    private var maxStreak: Int {
        appState.habits.map { $0.maxStreak }.max() ?? 0
    }

    private var totalCompleted: Int {
        appState.habits.filter { $0.todayComplete }.count
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {

                    // avatar + name
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

                    // achievements
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

                    // stats row
                    HStack(spacing: 0) {
                        statCell(value: "\(appState.habits.count)", label: "Habits")
                        Divider().frame(height: 40)
                        statCell(value: "\(totalCompleted)", label: "Done Today")
                        Divider().frame(height: 40)
                        statCell(value: "\(maxStreak)", label: "Best Streak")
                    }
                    .padding()
                    .background(Theme.white)
                    .cornerRadius(16)
                    .shadow(color: Theme.shadow, radius: 8, x: 0, y: 2)
                    .padding(.horizontal)

                    // settings
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

                    // sign out
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
            .onAppear {
                Task {
                    await appState.loadHabits()
                }
            }
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
}
