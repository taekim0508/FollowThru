import SwiftUI

struct CompletionModalView: View {
    @EnvironmentObject var appState: AppState
    @Environment(\.dismiss) private var dismiss

    let habit: Habit

    @State private var note = ""
    @State private var showNotes = false
    @State private var showCelebration = false

    var body: some View {
        VStack(spacing: 20) {
            Capsule()
                .fill(Theme.lightGray)
                .frame(width: 40, height: 5)
                .padding(.top, 12)

            Image(systemName: "leaf.arrow.circlepath")
                .font(.system(size: 40))
                .foregroundColor(Theme.sage)

            VStack(spacing: 4) {
                Text(habit.name)
                    .font(.title3).bold()
                    .foregroundColor(Theme.primary)
                if !habit.description.isEmpty {
                    Text(habit.description)
                        .font(.subheadline)
                        .foregroundColor(Theme.textSecondary)
                        .multilineTextAlignment(.center)
                }
            }

            Text("Did you complete this today?")
                .font(.subheadline)
                .foregroundColor(Theme.textSecondary)

            AppButton("Yes, I did it ✓", variant: .primary) { finish(completed: true) }

            // Add a note toggle
            Button {
                withAnimation { showNotes.toggle() }
            } label: {
                HStack {
                    Text("Add a note")
                        .font(.subheadline)
                        .foregroundColor(Theme.textSecondary)
                    Spacer()
                    Image(systemName: showNotes ? "chevron.up" : "chevron.down")
                        .foregroundColor(Theme.textSecondary)
                }
                .padding(.horizontal, 4)
            }

            if showNotes {
                TextEditor(text: $note)
                    .frame(height: 90)
                    .padding(8)
                    .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.softBlue.opacity(0.5)))
                    .transition(.opacity)
            }

            HStack(spacing: 12) {
                AppButton("Skip Today", variant: .secondary) { finish(completed: false) }
                AppButton("Not Yet", variant: .secondary) { dismiss() }
            }

            Spacer()
        }
        .padding(.horizontal, 24)
        .sheet(isPresented: $showCelebration) {
            CelebrationView()
                .presentationDetents([.medium])
        }
    }

    private func finish(completed: Bool) {
        if completed {
            appState.markComplete(habit: habit, note: note.isEmpty ? nil : note)
        }
        dismiss()
        if completed {
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                showCelebration = true
            }
        }
    }
}
