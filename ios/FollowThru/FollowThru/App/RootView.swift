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

            // commented out bc may be obsolete with progress view
            //CalendarView()
                //.tabItem { Label("Calendar", systemImage: "calendar") }
            
            InsightsView()
                .tabItem { Label("Insights", systemImage: "chart.xyaxis.line") }

            AIChatView()
                .tabItem { Label("AI", systemImage: "sparkles") }

            
            CommunityView()
                .tabItem { Label("Community", systemImage: "person.2") }
            
            
            ProfileView()
                .tabItem { Label("Profile", systemImage: "person") }
        }
        .accentColor(Theme.primary)
    }
}
