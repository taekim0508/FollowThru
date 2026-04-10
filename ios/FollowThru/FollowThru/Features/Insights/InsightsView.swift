import SwiftUI

struct InsightsView: View {
    @EnvironmentObject var appState: AppState
    @State private var selectedHabit: Habit? = nil

    var body: some View {
        NavigationStack {
            if let habit = selectedHabit {
                HabitAnalyticsView(habit: habit) {
                    selectedHabit = nil
                }
                .id(habit.id)  // Fix C — forces full rebuild when habit changes
                .environmentObject(appState)
            } else {
                habitSelector
            }
        }
    }

    // MARK: - Habit Selector

    private var habitSelector: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                if appState.habits.isEmpty {
                    emptyState
                } else {
                    Text("Select a habit to view analytics")
                        .font(.subheadline)
                        .foregroundColor(Theme.textSecondary)
                        .padding(.horizontal)
                        .padding(.top, 8)

                    LazyVStack(spacing: 12) {
                        ForEach(appState.habits) { habit in
                            habitCard(habit)
                                .padding(.horizontal)
                        }
                    }
                }
            }
            .padding(.bottom, 24)
        }
        .background(Theme.background.ignoresSafeArea())
        .navigationTitle("Insights")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            Task { await appState.loadHabits() }
        }
    }

    @ViewBuilder
    private func habitCard(_ habit: Habit) -> some View {
        Button {
            selectedHabit = habit
        } label: {
            HabitCard {
                VStack(alignment: .leading, spacing: 6) {
                    HStack {
                        Text(habit.name)
                            .font(.headline)
                            .foregroundColor(Theme.primary)
                        Spacer()
                        Image(systemName: "chevron.right")
                            .font(.caption)
                            .foregroundColor(Theme.textSecondary)
                    }

                    Text(habit.category)
                        .font(.caption)
                        .padding(.horizontal, 8).padding(.vertical, 2)
                        .background(Theme.sageLight)
                        .foregroundColor(Theme.sage)
                        .cornerRadius(8)

                    if !habit.description.isEmpty {
                        Text(habit.description)
                            .font(.subheadline)
                            .foregroundColor(Theme.textSecondary)
                            .lineLimit(2)
                    }

                    if let motivation = habit.motivationStatement, !motivation.isEmpty {
                        Text(motivation)
                            .font(.caption)
                            .foregroundColor(Theme.textSecondary)
                            .italic()
                            .lineLimit(2)
                    }
                }
            }
        }
        .buttonStyle(.plain)
    }

    private var emptyState: some View {
        VStack(spacing: 14) {
            Image(systemName: "chart.bar.xaxis")
                .font(.system(size: 48))
                .foregroundColor(Theme.sage)
            Text("No habits yet")
                .font(.headline)
            Text("Create a habit to start tracking insights")
                .font(.subheadline)
                .foregroundColor(Theme.textSecondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 80)
    }
}

// MARK: - Habit Analytics View

struct HabitAnalyticsView: View {
    @EnvironmentObject var appState: AppState
    let habit: Habit
    let onBack: () -> Void

    @State private var binaryAnalytics: BinaryAnalytics? = nil
    @State private var trackedAnalytics: TrackedAnalytics? = nil
    @State private var isLoading = false
    @State private var error: String? = nil

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {

                // Fix B — animate loading transition
                Group {
                    if isLoading {
                        InsightsView()
                            .frame(maxWidth: .infinity)
                            .padding(.top, 40)
                    } else if let error = error {
                        Text(error)
                            .font(.subheadline)
                            .foregroundColor(.red)
                            .padding(.horizontal)
                    } else if habit.habitType == "binary" {
                        if let analytics = binaryAnalytics {
                            if analytics.totalCompletions == 0 {
                                emptyState
                            } else {
                                binaryContent(analytics)
                            }
                        }
                    } else {
                        if let analytics = trackedAnalytics {
                            if analytics.completedDays == 0 {
                                emptyState
                            } else {
                                trackedContent(analytics)
                            }
                        }
                    }
                }
                .animation(.easeInOut(duration: 0.2), value: isLoading)
            }
            .padding(.vertical)
        }
        .background(Theme.background.ignoresSafeArea())
        .navigationTitle(habit.name)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarLeading) {
                Button {
                    onBack()
                } label: {
                    Image(systemName: "chevron.left")
                        .foregroundColor(Theme.primary)
                }
            }
        }
        .task {
            await loadAnalytics()
        }
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: 12) {
            Image(systemName: "chart.bar.xaxis")
                .font(.system(size: 48))
                .foregroundColor(Theme.sage)
            Text("Complete this habit to start seeing analytics")
                .font(.subheadline)
                .foregroundColor(Theme.textSecondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 40)
        .padding(.horizontal)
    }

    // MARK: - Binary Content

    @ViewBuilder
    private func binaryContent(_ analytics: BinaryAnalytics) -> some View {
        binaryChart(analytics)
            .padding(.horizontal)
        binaryStatsGrid(analytics)
            .padding(.horizontal)
    }

    @ViewBuilder
    private func binaryChart(_ analytics: BinaryAnalytics) -> some View {
        HabitCard {
            VStack(alignment: .leading, spacing: 12) {
                Text(habit.name)
                    .font(.headline)
                    .foregroundColor(Theme.primary)

                // week only — always show dot grid
                binaryDotGrid(analytics.bars)
            }
        }
    }

    @ViewBuilder
    private func binaryDotGrid(_ bars: [BinaryBar]) -> some View {
        VStack(spacing: 8) {
            // single row with day labels above dots
            HStack {
                ForEach(bars) { bar in
                    VStack(spacing: 4) {
                        Text(bar.label)
                            .font(.caption2)
                            .foregroundColor(Theme.textSecondary)
                        dotCell(bar)
                    }
                    .frame(maxWidth: .infinity)
                }
            }

            // legend
            HStack(spacing: 16) {
                legendItem(color: Theme.sage, label: "Completed")
                legendItem(color: Theme.terracotta.opacity(0.3), label: "Missed")
                legendItem(color: Theme.lightGray, label: "Not scheduled")
            }
            .padding(.top, 4)
        }
    }

    @ViewBuilder
    private func dotCell(_ bar: BinaryBar) -> some View {
        let color: Color = {
            if bar.isFuture { return Theme.lightGray.opacity(0.3) }
            if !bar.isScheduled { return Theme.lightGray.opacity(0.4) }
            if bar.isComplete { return Theme.sage }
            return Theme.terracotta.opacity(0.3)
        }()

        RoundedRectangle(cornerRadius: 4)
            .fill(color)
            .frame(width: 28, height: 28)
    }

    // MARK: - Tracked Content

    @ViewBuilder
    private func trackedContent(_ analytics: TrackedAnalytics) -> some View {
        trackedChart(analytics)
            .padding(.horizontal)
        trackedStatsGrid(analytics)
            .padding(.horizontal)
    }

    @ViewBuilder
    private func trackedChart(_ analytics: TrackedAnalytics) -> some View {
        HabitCard {
            VStack(alignment: .leading, spacing: 12) {
                Text(habit.name)
                    .font(.headline)
                    .foregroundColor(Theme.primary)

                // week only — always show daily bars
                trackedDailyBars(analytics)
            }
        }
    }

    @ViewBuilder
    private func trackedDailyBars(_ analytics: TrackedAnalytics) -> some View {
        let maxValue = max(
            analytics.bars.compactMap { $0.value }.max() ?? 0,
            analytics.targetValue ?? 0
        )
        let chartHeight: CGFloat = 80

        VStack(alignment: .leading, spacing: 8) {
            ScrollView(.horizontal, showsIndicators: false) {
                ZStack(alignment: .bottomLeading) {
                    // bars
                    HStack(alignment: .bottom, spacing: 6) {
                        ForEach(analytics.bars) { bar in
                            VStack(spacing: 4) {
                                ZStack(alignment: .bottom) {
                                    // background — scheduled but empty
                                    RoundedRectangle(cornerRadius: 4)
                                        .fill(bar.isScheduled == true && !bar.isFuture
                                            ? Theme.lightGray.opacity(0.3) : Color.clear)
                                        .frame(width: 24, height: chartHeight)

                                    // value bar
                                    if let value = bar.value, value > 0, maxValue > 0 {
                                        RoundedRectangle(cornerRadius: 4)
                                            .fill(bar.isComplete == true ? Theme.sage : Theme.textTertiary)
                                            .frame(
                                                width: 24,
                                                height: max(4, CGFloat(value / maxValue) * chartHeight)
                                            )
                                    }
                                }
                                .frame(height: chartHeight)

                                Text(bar.label)
                                    .font(.caption2)
                                    .foregroundColor(Theme.textSecondary)
                                    .frame(width: 24)
                            }
                        }
                    }
                }
                .padding(.vertical, 8)
            }

            // legend
            HStack(spacing: 16) {
                legendItem(color: Theme.sage, label: "Goal met")
                legendItem(color: Theme.textTertiary, label: "Partial")
            }
        }
    }

    // MARK: - Stats Grids

    @ViewBuilder
    private func binaryStatsGrid(_ analytics: BinaryAnalytics) -> some View {
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
            statCard(
                icon: "flame.fill",
                color: Theme.terracotta,
                value: "\(analytics.currentStreak)",
                label: "Current Streak",
                suffix: "days"
            )
            statCard(
                icon: "trophy.fill",
                color: Theme.sage,
                value: "\(analytics.maxStreak)",
                label: "Longest Streak",
                suffix: "days"
            )
            statCard(
                icon: "percent",
                color: Theme.primary,
                value: "\(analytics.completionRate)%",
                label: "Completion Rate",
                suffix: nil
            )
            statCard(
                icon: "checkmark.circle.fill",
                color: Theme.sage,
                value: "\(analytics.totalCompletions)",
                label: "Total Completions",
                suffix: nil
            )
        }
    }

    @ViewBuilder
    private func trackedStatsGrid(_ analytics: TrackedAnalytics) -> some View {
        let unit = analytics.quantityUnit ?? ""
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
            statCard(
                icon: "flame.fill",
                color: Theme.terracotta,
                value: "\(analytics.currentStreak)",
                label: "Current Streak",
                suffix: "days"
            )
            statCard(
                icon: "trophy.fill",
                color: Theme.sage,
                value: "\(analytics.maxStreak)",
                label: "Longest Streak",
                suffix: "days"
            )
            statCard(
                icon: "percent",
                color: Theme.primary,
                value: "\(analytics.completionRate)%",
                label: "Completion Rate",
                suffix: nil
            )
            if let total = analytics.totalValue {
                statCard(
                    icon: "sum",
                    color: Theme.sage,
                    value: formatValue(total),
                    label: "Total",
                    suffix: unit
                )
            }
            if let avg = analytics.dailyAverage {
                statCard(
                    icon: "chart.line.uptrend.xyaxis",
                    color: Theme.primary,
                    value: formatValue(avg),
                    label: "Daily Average",
                    suffix: unit
                )
            }
            if let best = analytics.personalBest {
                statCard(
                    icon: "star.fill",
                    color: Theme.terracotta,
                    value: formatValue(best),
                    label: "Personal Best",
                    suffix: unit
                )
            }
        }
    }

    @ViewBuilder
    private func statCard(
        icon: String,
        color: Color,
        value: String,
        label: String,
        suffix: String?
    ) -> some View {
        HabitCard {
            VStack(alignment: .leading, spacing: 6) {
                Image(systemName: icon)
                    .foregroundColor(color)
                    .font(.system(size: 20))

                HStack(alignment: .lastTextBaseline, spacing: 4) {
                    Text(value)
                        .font(.system(size: 28, weight: .bold))
                        .foregroundColor(Theme.primary)
                    if let suffix = suffix, !suffix.isEmpty {
                        Text(suffix)
                            .font(.caption)
                            .foregroundColor(Theme.textSecondary)
                    }
                }

                Text(label)
                    .font(.caption)
                    .foregroundColor(Theme.textSecondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    // MARK: - Helpers

    @ViewBuilder
    private func legendItem(color: Color, label: String) -> some View {
        HStack(spacing: 4) {
            RoundedRectangle(cornerRadius: 2)
                .fill(color)
                .frame(width: 10, height: 10)
            Text(label)
                .font(.caption2)
                .foregroundColor(Theme.textSecondary)
        }
    }

    private func barColor(_ color: String) -> Color {
        switch color {
        case "green": return Theme.sage
        case "orange": return Theme.terracotta.opacity(0.7)
        default: return Theme.lightGray.opacity(0.4)
        }
    }

    private func formatValue(_ value: Double) -> String {
        if value.truncatingRemainder(dividingBy: 1) == 0 {
            return String(Int(value))
        }
        return String(format: "%.1f", value)
    }

    // MARK: - Data Loading

    private func loadAnalytics() async {
        isLoading = true
        error = nil
        do {
            if habit.habitType == "binary" {
                binaryAnalytics = try await AnalyticsAPI.binaryAnalytics(habitId: habit.id)
            } else {
                trackedAnalytics = try await AnalyticsAPI.trackedAnalytics(habitId: habit.id)
            }
        } catch {
            self.error = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        }
        isLoading = false
    }
}
