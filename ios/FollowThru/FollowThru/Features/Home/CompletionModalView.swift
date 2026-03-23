import SwiftUI

struct CompletionModalView: View {
    @EnvironmentObject var appState: AppState
    @Environment(\.dismiss) private var dismiss

    let habit: Habit

    @State private var note = ""
    @State private var showNotes = false
    @State private var showCelebration = false
    @State private var logValue: String = ""

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

            // Different UI based on KPI type
            switch habit.kpiType {
            case .checkbox:
                checkboxUI
            case .duration:
                valueUI(unit: "min", icon: "clock")
            case .count:
                valueUI(unit: "times", icon: "number")
            }

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

    // MARK: - KPI UI

    private var checkboxUI: some View {
        AppButton("Yes, I did it ✓", variant: .primary) {
            finish(completed: true)
        }
    }

    private func valueUI(unit: String, icon: String) -> some View {
        VStack(spacing: 12) {
            // Target hint
            if let target = habit.kpiTarget {
                Text("Your goal: \(Int(target)) \(unit)")
                    .font(.subheadline)
                    .foregroundColor(Theme.textSecondary)
            }

            // Value input
            HStack {
                Image(systemName: icon)
                    .foregroundColor(Theme.primary)
                TextField("0", text: $logValue)
                    .keyboardType(.numberPad)
                    .font(.title2).fontWeight(.semibold)
                    .foregroundColor(Theme.primary)
                Text(unit)
                    .foregroundColor(Theme.textSecondary)
                    .fontWeight(.semibold)
            }
            .padding(14)
            .background(Theme.white)
            .cornerRadius(12)
            .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.lightGray))

            // Progress hint if they've typed something
            if let entered = Double(logValue), let target = habit.kpiTarget {
                let met = entered >= target
                HStack(spacing: 4) {
                    Image(systemName: met ? "checkmark.circle.fill" : "minus.circle")
                        .foregroundColor(met ? Theme.sage : Theme.terracotta)
                    Text(met ? "Goal reached!" : "\(Int(target - entered)) \(unit) to go")
                        .font(.caption)
                        .foregroundColor(met ? Theme.sage : Theme.terracotta)
                }
                .transition(.opacity)
                .animation(.easeInOut, value: logValue)
            }

            AppButton("Log \(unit == "min" ? "Duration" : "Amount") ✓", variant: .primary) {
                finishWithValue()
            }
            .disabled(logValue.isEmpty)
            .opacity(logValue.isEmpty ? 0.5 : 1)
        }
    }

    // MARK: - Logic

    private func finishWithValue() {
        let entered = Double(logValue) ?? 0
        let target = habit.kpiTarget ?? 0
        let completed = entered >= target
        appState.markComplete(habit: habit, value: entered, note: note.isEmpty ? nil : note, completed: completed)
        dismiss()
        if completed {
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                showCelebration = true
            }
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
