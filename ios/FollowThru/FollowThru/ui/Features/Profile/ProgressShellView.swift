import SwiftUI

struct ProgressShellView: View {
    var body: some View {
        NavigationStack {
            VStack(spacing: 14) {
                Spacer()
                Image(systemName: "chart.bar.xaxis")
                    .font(.system(size: 52))
                    .foregroundColor(Theme.softBlue)
                Text("Progress")
                    .font(.title2).bold()
                    .foregroundColor(Theme.primary)
                Text("Analytics and insights coming soon")
                    .font(.subheadline)
                    .foregroundColor(Theme.textSecondary)
                Spacer()
            }
            .frame(maxWidth: .infinity)
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("Progress")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}

struct CommunityView: View {
    var body: some View {
        NavigationStack {
            VStack(spacing: 14) {
                Spacer()
                Image(systemName: "person.2")
                    .font(.system(size: 52))
                    .foregroundColor(Theme.softBlue)
                Text("Community")
                    .font(.title2).bold()
                    .foregroundColor(Theme.primary)
                Text("Social features coming soon")
                    .font(.subheadline)
                    .foregroundColor(Theme.textSecondary)
                Spacer()
            }
            .frame(maxWidth: .infinity)
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("Community")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}
