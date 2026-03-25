import SwiftUI

struct HomeView: View {
    @EnvironmentObject var appState: AppState
    @State private var showCreate = false
    @State private var selectedHabitForDetail: Habit? = nil

    private var greeting: String {
        let h = Calendar.current.component(.hour, from: Date())
        if h < 12 { return "Good morning" }
        if h < 17 { return "Good afternoon" }
        return "Good evening"
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {

                    // Header
                    VStack(alignment: .leading, spacing: 4) {
                        Text("\(greeting), \(appState.currentUser?.username ?? "there") 👋")
                            .font(.title2).bold()
                            .foregroundColor(Theme.primary)
                        Text(Date(), style: .date)
                            .font(.subheadline)
                            .foregroundColor(Theme.textSecondary)
                    }
                    .padding(.horizontal)
                    .padding(.top, 8)

                    if appState.isHabitsLoading {
                        ProgressView()
                            .frame(maxWidth: .infinity)
                            .padding(.top, 40)
                    } else if appState.habits.isEmpty {
                        emptyState
                    } else {
                        // Today's progress summary
                        progressCard
                            .padding(.horizontal)

                        // Section 1 — scheduled today, not yet complete
                        let pending = appState.todaysHabits.filter { !$0.todayComplete }
                        if !pending.isEmpty {
                            sectionHeader("Today")
                            LazyVStack(spacing: 12) {
                                ForEach(pending) { habit in
                                    habitRow(habit)
                                        .padding(.horizontal)
                                }
                            }
                        }

                        // Section 2 — scheduled today, already complete
                        let completed = appState.todaysHabits.filter { $0.todayComplete }
                        if !completed.isEmpty {
                            sectionHeader("Completed")
                            LazyVStack(spacing: 12) {
                                ForEach(completed) { habit in
                                    habitRow(habit)
                                        .padding(.horizontal)
                                }
                            }
                        }

                        // Section 3 — not scheduled today
                        if !appState.nonTodayHabits.isEmpty {
                            sectionHeader("Not Today")
                            LazyVStack(spacing: 12) {
                                ForEach(appState.nonTodayHabits) { habit in
                                    habitRow(habit, dimmed: true)
                                        .padding(.horizontal)
                                }
                            }
                        }
                    }

                    if let error = appState.habitsError {
                        Text(error)
                            .font(.footnote)
                            .foregroundColor(.red)
                            .padding(.horizontal)
                    }
                }
                .padding(.bottom, 24)
            }
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("HabitFlow")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button { showCreate = true } label: {
                        Image(systemName: "plus")
                            .font(.system(size: 17, weight: .semibold))
                            .foregroundColor(Theme.primary)
                    }
                }
            }
            .sheet(isPresented: $showCreate) {
                CreateHabitView()
            }
            .sheet(item: $selectedHabitForDetail) { habit in
                HabitDetailView(habit: habit)
                    .environmentObject(appState)
            }
            .sheet(item: $appState.selectedHabit) { habit in
                CompletionModalView(habit: habit)
                    .presentationDetents([.medium])
            }
            .onAppear {
                Task {
                    await appState.loadHabits()
                }
            }
        }
    }

    // MARK: - Subviews

    private var progressCard: some View {
        let total = appState.todaysHabits.count
        let done = appState.todaysHabits.filter { $0.todayComplete }.count
        let pct = total > 0 ? Double(done) / Double(total) : 0

        return HabitCard {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Text("Today's Progress")
                        .font(.subheadline).fontWeight(.semibold)
                    Spacer()
                    Text("\(done)/\(total) habits")
                        .font(.caption)
                        .foregroundColor(Theme.textSecondary)
                }
                HabitProgressBar(value: pct)
                    .frame(height: 6)
            }
        }
    }

    @ViewBuilder
    private func sectionHeader(_ title: String) -> some View {
        Text(title)
            .font(.subheadline)
            .fontWeight(.semibold)
            .foregroundColor(Theme.textSecondary)
            .padding(.horizontal)
            .padding(.top, 8)
    }

    @ViewBuilder
    private func habitRow(_ habit: Habit, dimmed: Bool = false) -> some View {
        HabitCard {
            HStack(spacing: 12) {
                // icon
                Circle()
                    .fill(habit.todayComplete ? Theme.sage : Theme.softBlue.opacity(0.25))
                    .frame(width: 44, height: 44)
                    .overlay(
                        Image(systemName: habit.todayComplete ? "checkmark" : habitIcon(habit))
                            .foregroundColor(habit.todayComplete ? Theme.white : Theme.softBlue)
                            .font(.system(size: 16, weight: .semibold))
                    )

                // name + meta
                VStack(alignment: .leading, spacing: 3) {
                    Text(habit.name)
                        .font(.headline)
                        .foregroundColor(dimmed ? Theme.textSecondary : Theme.primary)

                    HStack(spacing: 6) {
                        // habit type badge
                        Text(habit.habitType == "binary" ? "Completion" : "Numeric")
                            .font(.caption)
                            .padding(.horizontal, 8).padding(.vertical, 2)
                            .background(Theme.sageLight)
                            .cornerRadius(8)

                        // streak badge
                        if habit.currentStreak > 0 {
                            Label("\(habit.currentStreak)", systemImage: "flame.fill")
                                .font(.caption)
                                .foregroundColor(Theme.terracotta)
                        }

                        // progress for tracked habits
                        if habit.habitType == "tracked", let progress = habit.todayProgress {
                            let target = habit.targetValue ?? 0
                            let unit = habit.quantityUnit ?? ""
                            Text("\(Int(progress))/\(Int(target)) \(unit)")
                                .font(.caption)
                                .foregroundColor(Theme.textSecondary)
                        }
                    }
                    
                    // motivation statement — only show if present
                    if let motivation = habit.motivationStatement, !motivation.isEmpty {
                        Text(motivation)
                            .font(.caption)
                            .foregroundColor(Theme.textSecondary)
                            .italic()
                            .fixedSize(horizontal: false, vertical: true)  // allows vertical growth
                            .padding(.top, 2)
                    }
                }

                Spacer()

                // action button — only for today's habits
                if !dimmed {
                    if habit.todayComplete && habit.habitType == "binary" {
                        // completed binary — show checkmark, no button
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundColor(Theme.sage)
                            .font(.system(size: 22))
                    } else if habit.habitType == "binary" {
                        // binary button
                        AppButton("Done", variant: .compact, colorStyle: .action) {
                            appState.selectedHabit = habit
                        }
                        .fixedSize()
                    } else {
                        // numeric button
                        AppButton(
                            habit.todayProgress != nil ? "Update" : "Log",
                            variant: .compact,
                            colorStyle: .action
                        ) {
                            appState.selectedHabit = habit
                        }
                        .fixedSize()
                    }
                }
            }
        }
        .opacity(dimmed ? 0.5 : 1.0)
        .onTapGesture {
            selectedHabitForDetail = habit
        }
    }

    private var emptyState: some View {
        VStack(spacing: 14) {
            Image(systemName: "list.bullet.clipboard")
                .font(.system(size: 48))
                .foregroundColor(Theme.softBlue)
            Text("No habits yet")
                .font(.headline)
            Text("Tap + to create your first habit")
                .font(.subheadline)
                .foregroundColor(Theme.textSecondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 80)
    }

    private func habitIcon(_ habit: Habit) -> String {
        if habit.habitType == "binary" { return "checkmark" }
        if habit.quantityUnit == "minutes" { return "clock" }
        return "number"
    }
}
