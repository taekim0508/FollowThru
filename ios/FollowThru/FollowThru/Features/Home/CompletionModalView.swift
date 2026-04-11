import SwiftUI

struct CompletionModalView: View {
    @EnvironmentObject var appState: AppState
    @Environment(\.dismiss) private var dismiss

    let habit: Habit

    @State private var note = ""
    @State private var showNotes = false
    @State private var showCelebration = false
    @State private var progressString = ""
    @State private var isLoading = false

    // pre-populate with existing progress if already logged today
    private var existingProgress: String {
        if let p = habit.todayProgress { return String(Int(p)) }
        return ""
    }

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
                // motivation — show below description if present
                if let motivation = habit.motivationStatement, !motivation.isEmpty {
                    Text("\(motivation)")
                        .font(.caption)
                        .foregroundColor(Theme.textSecondary)
                        .italic()
                        .multilineTextAlignment(.center)
                        .padding(.top, 2)
                }
            }

            if habit.habitType == "binary" {
                binaryUI
            } else {
                trackedUI
            }

            // notes toggle
            Button {
                withAnimation { showNotes.toggle() }
            } label: {
                HStack {
                    Text(showNotes ? "Hide note" : "Add a note")
                        .font(.subheadline)
                        .foregroundColor(Theme.textSecondary)
                    Spacer()
                    Image(systemName: showNotes ? "chevron.up" : "chevron.down")
                        .foregroundColor(Theme.textSecondary)
                }
                .padding(.horizontal, 4)
            }

            if showNotes {
                ZStack(alignment: .topLeading) {
                    if note.isEmpty {
                        Text("Add a note...")
                            .foregroundColor(Theme.textSecondary)
                            .padding(.top, 16)
                            .padding(.leading, 12)
                            .allowsHitTesting(false)
                    }
                    TextEditor(text: $note)
                        .foregroundColor(Theme.primary)
                        .frame(height: 90)
                }
                .padding(4)
                .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.lightGray))
                .transition(.opacity)
            }

            if isLoading {
                ProgressView()
            }

            Spacer()
        }
        .padding(.horizontal, 24)
        .onAppear {
            // pre-populate progress if already logged today
            progressString = existingProgress
        }
        .sheet(isPresented: $showCelebration) {
            CelebrationView()
                .presentationDetents([.medium])
        }
    }

    // MARK: - Binary UI

    private var binaryUI: some View {
        VStack(spacing: 12) {
            AppButton(
                habit.todayComplete ? "Already done ✓" : "Yes, I did it ✓",
                variant: .primary
            ) {
                guard !habit.todayComplete else { return }
                complete()
            }
            .disabled(habit.todayComplete || isLoading)
            .opacity(habit.todayComplete ? 0.6 : 1)

            // only show if not already completed
            if !habit.todayComplete {
                AppButton("No I didn't", variant: .secondary) {
                    dismiss()
                }
            }
        }
    }

    // MARK: - Tracked UI

    private var trackedUI: some View {
        VStack(spacing: 12) {
            // target hint
            if let target = habit.targetValue {
                let unit = habit.quantityUnit ?? ""
                Text("Goal: \(Int(target)) \(unit)")
                    .font(.subheadline)
                    .foregroundColor(Theme.textSecondary)
            }

            // value input
            HStack {
                Image(systemName: habit.quantityUnit == "minutes" ? "clock" : "number")
                    .foregroundColor(Theme.primary)
                TextField("0", text: $progressString)
                    .keyboardType(.decimalPad)
                    .font(.title2).fontWeight(.semibold)
                    .foregroundColor(Theme.primary)
                if let unit = habit.quantityUnit {
                    Text(unit)
                        .foregroundColor(Theme.textSecondary)
                        .fontWeight(.semibold)
                }
            }
            .padding(14)
            .background(Theme.white)
            .cornerRadius(12)
            .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.lightGray))

            // progress feedback
            if let entered = Double(progressString), let target = habit.targetValue {
                let met = entered >= target
                let unit = habit.quantityUnit ?? ""
                HStack(spacing: 4) {
                    Image(systemName: met ? "checkmark.circle.fill" : "minus.circle")
                        .foregroundColor(met ? Theme.sage : Theme.terracotta)
                    Text(met ? "Goal reached!" : "\(Int(target - entered)) \(unit) to go")
                        .font(.caption)
                        .foregroundColor(met ? Theme.sage : Theme.terracotta)
                }
                .animation(.easeInOut, value: progressString)
            }

            AppButton("Log \(habit.quantityUnit ?? "progress")", variant: .primary) {
                logProgress()
            }
            .disabled(progressString.isEmpty || Double(progressString) == nil || isLoading)
            .opacity(progressString.isEmpty ? 0.5 : 1)
        }
    }

    // MARK: - Actions

    private func complete() {
        isLoading = true
        Task {
            await appState.completeHabit(habit, note: note.isEmpty ? nil : note)
            isLoading = false
            dismiss()
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                showCelebration = true
            }
        }
    }

    private func logProgress() {
        guard let value = Double(progressString) else { return }
        let wasComplete = habit.todayComplete
        isLoading = true
        Task {
            await appState.logProgress(habit, progressValue: value, note: note.isEmpty ? nil : note)
            isLoading = false
            dismiss()
            // only show celebration if this log crossed the completion threshold
            if !wasComplete, value >= (habit.targetValue ?? 0) {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                    showCelebration = true
                }
            }
        }
    }
}
