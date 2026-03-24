import SwiftUI

struct RootView: View {
    @EnvironmentObject var appState: AppState

    var body: some View {
        Group {
            if appState.isAuthenticated {
                MainTabView()
            } else {
                AuthView()
            }
        }
        .animation(.easeInOut(duration: 0.25), value: appState.isAuthenticated)
    }
}

struct MainTabView: View {
    @EnvironmentObject var appState: AppState

    var body: some View {
        TabView {
            HomeView()
                .tabItem { Label("Home", systemImage: "house") }

            CalendarView()
                .tabItem { Label("Calendar", systemImage: "calendar") }

            AIChatView()
                .tabItem { Label("AI", systemImage: "sparkles") }

            
            CommunityView()
                .tabItem { Label("Community", systemImage: "person.2") }
            
            // moved progress tab up one, so it is in the same supertab as profile ("... more")
            ProgressShellView()
                .tabItem { Label("Progress", systemImage: "chart.bar") }

            ProfileView()
                .tabItem { Label("Profile", systemImage: "person") }
        }
        .accentColor(Theme.primary)
        .sheet(isPresented: $appState.showCompletionModal) {
            if let habit = appState.selectedHabit {
                CompletionModalView(habit: habit)
                    .presentationDetents([.medium])
            }
        }
    }
}
