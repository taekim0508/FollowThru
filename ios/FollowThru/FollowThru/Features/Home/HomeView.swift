import SwiftUI

struct HomeView: View {
    @EnvironmentObject var appState: AppState
    @State private var showCreate = false
    @State private var showCelebration = false
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

                    // Progress summary
                    if !appState.habits.isEmpty {
                        progressCard
                            .padding(.horizontal)
                    }

                    // Habit list
                    if appState.habits.isEmpty {
                        emptyState
                    } else {
                        LazyVStack(spacing: 12) {
                            ForEach(appState.habits) { habit in
                                habitRow(habit)
                                    .padding(.horizontal)
                            }
                        }
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
            .sheet(isPresented: $showCelebration) {
                CelebrationView()
                    .presentationDetents([.medium])
            }
            .sheet(isPresented: $showCreate) {
                CreateHabitView()
            }
            .sheet(item: $selectedHabitForDetail) { habit in
                HabitDetailView(habit: habit)
                    .environmentObject(appState)
            }
        }
    }

    // MARK: - Subviews

    private var progressCard: some View {
        let total = appState.habits.count
        let done = appState.habits.filter { appState.isCompleted(habit: $0) }.count
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
    private func habitRow(_ habit: Habit) -> some View {
        let done = appState.isCompleted(habit: habit)
        HabitCard {
            HStack(spacing: 12) {
                Circle()
                    .fill(done ? Theme.sage : Theme.softBlue.opacity(0.25))
                    .frame(width: 44, height: 44)
                    .overlay(
                        Image(systemName: done ? "checkmark" : kpiIcon(habit.kpiType))
                            .foregroundColor(done ? Theme.white : Theme.softBlue)
                            .font(.system(size: 16, weight: .semibold))
                    )

                VStack(alignment: .leading, spacing: 3) {
                    Text(habit.name).font(.headline)
                    HStack(spacing: 6) {
                        Text(habit.kpiType.rawValue)
                            .font(.caption)
                            .padding(.horizontal, 8).padding(.vertical, 2)
                            .background(Theme.sageLight)
                            .cornerRadius(8)
                        if habit.streak > 0 {
                            Label("\(habit.streak)", systemImage: "flame.fill")
                                .font(.caption)
                                .foregroundColor(Theme.terracotta)
                        }
                    }
                }

                Spacer()

                if done {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(Theme.sage)
                        .font(.system(size: 22))
                } else {
                    AppButton("Done", variant: .compact, colorStyle: .action) {
                        appState.selectedHabit = habit
                        appState.showCompletionModal = true
                    }
                }
            }
        }
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

    private func kpiIcon(_ type: KPIType) -> String {
        switch type {
        case .checkbox: return "checkmark"
        case .duration: return "clock"
        case .count:    return "number"
        }
    }
}
