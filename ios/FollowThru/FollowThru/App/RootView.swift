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

            ProgressShellView()
                .tabItem { Label("Progress", systemImage: "chart.bar") }

            /* Commented out for cleaner look for now. iOS only allows 5 tabs; decisions to be made here*/
            //CommunityView()
                //.tabItem { Label("Community", systemImage: "person.2") }

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
