import SwiftUI

struct CelebrationView: View {
    @EnvironmentObject var appState: AppState
    @Environment(\.dismiss) private var dismiss

    @State private var scale: CGFloat = 0.5
    @State private var countdown = 3

    private var streak: Int {
        appState.selectedHabit.flatMap { habit in
            appState.habits.first(where: { $0.id == habit.id })?.streak
        } ?? 0
    }

    var body: some View {
        VStack(spacing: 24) {
            Spacer()

            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 80))
                .foregroundColor(Theme.sage)
                .scaleEffect(scale)
                .onAppear {
                    withAnimation(.spring(response: 0.5, dampingFraction: 0.6)) {
                        scale = 1.0
                    }
                }

            Text("Well done!")
                .font(.largeTitle).bold()
                .foregroundColor(Theme.primary)

            if streak > 0 {
                VStack(spacing: 4) {
                    HStack(spacing: 6) {
                        Image(systemName: "flame.fill").foregroundColor(Theme.terracotta)
                        Text("\(streak)").font(.system(size: 40, weight: .bold)).foregroundColor(Theme.terracotta)
                    }
                    Text("day streak").font(.subheadline).foregroundColor(Theme.textSecondary)
                }
            }

            Text("\"Consistency is more important than perfection\"")
                .font(.caption)
                .foregroundColor(Theme.textSecondary)
                .italic()
                .multilineTextAlignment(.center)
                .padding(.horizontal)

            Spacer()

            AppButton("Continue", variant: .primary) { dismiss() }
                .padding(.horizontal)

            Text(countdown > 0 ? "Closing in \(countdown)…" : "")
                .font(.caption)
                .foregroundColor(Theme.textSecondary)
                .padding(.bottom, 16)
        }
        .background(Theme.background.ignoresSafeArea())
        .onAppear { startCountdown() }
    }

    private func startCountdown() {
        Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { t in
            if countdown <= 1 {
                t.invalidate()
                dismiss()
            } else {
                countdown -= 1
            }
        }
    }
}
