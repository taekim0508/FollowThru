import SwiftUI

struct CalendarView: View {
    @EnvironmentObject var appState: AppState
    @State private var displayMonth = Date()
    @State private var selectedHabit: Habit? = nil  // nil = "All"

    private let cal = Calendar.current
    private let columns = Array(repeating: GridItem(.flexible()), count: 7)
    private let weekdayHeaders = ["SUN","MON","TUE","WED","THU","FRI","SAT"]

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {

                    // Habit picker
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 8) {

                            // All pill — always first
                            Button { selectedHabit = nil } label: {
                                Text("All")
                                    .font(.subheadline).fontWeight(selectedHabit == nil ? .semibold : .regular)
                                    .padding(.horizontal, 14).padding(.vertical, 8)
                                    .background(selectedHabit == nil ? Theme.primary : Theme.offWhite)
                                    .foregroundColor(selectedHabit == nil ? Theme.white : Theme.textSecondary)
                                    .cornerRadius(20)
                            }

                            // Separator
                            if !appState.habits.isEmpty {
                                Rectangle()
                                    .fill(Theme.lightGray)
                                    .frame(width: 1, height: 24)
                                    .padding(.horizontal, 2)
                            }

                            ForEach(appState.habits) { habit in
                                let selected = selectedHabit?.id == habit.id
                                Button { selectedHabit = habit } label: {
                                    Text(habit.name)
                                        .font(.subheadline).fontWeight(selected ? .semibold : .regular)
                                        .padding(.horizontal, 14).padding(.vertical, 8)
                                        .background(selected ? Theme.primary : Theme.offWhite)
                                        .foregroundColor(selected ? Theme.white : Theme.textSecondary)
                                        .cornerRadius(20)
                                }
                            }
                        }
                        .padding(.horizontal)
                    }

                    // Month navigation
                    HStack {
                        Button { shiftMonth(-1) } label: {
                            Image(systemName: "chevron.left")
                                .foregroundColor(Theme.primary)
                                .padding(8)
                        }
                        Spacer()
                        Text(displayMonth, formatter: monthFormatter)
                            .font(.headline)
                            .foregroundColor(Theme.primary)
                        Spacer()
                        Button { shiftMonth(1) } label: {
                            Image(systemName: "chevron.right")
                                .foregroundColor(Theme.primary)
                                .padding(8)
                        }
                    }
                    .padding(.horizontal)

                    // Calendar grid
                    VStack(spacing: 4) {
                        HStack {
                            ForEach(weekdayHeaders, id: \.self) { d in
                                Text(d)
                                    .font(.caption).fontWeight(.semibold)
                                    .foregroundColor(Theme.textSecondary)
                                    .frame(maxWidth: .infinity)
                            }
                        }
                        .padding(.horizontal)

                        LazyVGrid(columns: columns, spacing: 6) {
                            ForEach(Array(gridDays().enumerated()), id: \.offset) { _, date in
                                dayCell(date)
                            }
                        }
                        .padding(.horizontal)
                    }

                    // Stats
                    if let habit = selectedHabit {
                        statsCard(habit: habit)
                            .padding(.horizontal)
                    } else {
                        allStatsCard
                            .padding(.horizontal)
                    }
                }
                .padding(.vertical)
            }
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("Calendar")
            .navigationBarTitleDisplayMode(.inline)
            .onChange(of: appState.habits.count) { _ in
                // If selected habit was deleted, fall back to All
                if let selected = selectedHabit, !appState.habits.contains(where: { $0.id == selected.id }) {
                    selectedHabit = nil
                }
            }
        }
    }

    // MARK: - Grid

    private func gridDays() -> [Date?] {
        guard let monthStart = cal.date(from: cal.dateComponents([.year, .month], from: displayMonth)),
              let range = cal.range(of: .day, in: .month, for: monthStart) else { return [] }

        let firstWeekday = cal.component(.weekday, from: monthStart) - 1
        var days: [Date?] = Array(repeating: nil, count: firstWeekday)

        for day in range {
            if let date = cal.date(byAdding: .day, value: day - 1, to: monthStart) {
                days.append(date)
            }
        }

        while days.count % 7 != 0 { days.append(nil) }
        return days
    }

    @ViewBuilder
    private func dayCell(_ date: Date?) -> some View {
        if let date = date {
            let status = selectedHabit != nil ? dayStatus(date) : allDayStatus(date)
            let dayNum = cal.component(.day, from: date)
            let isToday = cal.isDateInToday(date)

            ZStack {
                Circle()
                    .fill(cellColor(status))
                    .frame(width: 34, height: 34)
                    .overlay(
                        Circle().strokeBorder(isToday ? Theme.primary : Color.clear, lineWidth: 2)
                    )
                Text("\(dayNum)")
                    .font(.caption).fontWeight(isToday ? .bold : .regular)
                    .foregroundColor(cellTextColor(status))
            }
            .frame(height: 38)
        } else {
            Color.clear.frame(height: 38)
        }
    }

    // MARK: - Day Status

    private enum DayStatus { case completed, partial, missed, future, unscheduled }

    private func dayStatus(_ date: Date) -> DayStatus {
        guard let habit = selectedHabit else { return .unscheduled }
        if date > Date() { return .future }

        let log = appState.logs.first {
            $0.habitId == habit.id && cal.isDate($0.date, inSameDayAs: date)
        }
        if let log = log { return log.completed ? .completed : .missed }

        let weekday = cal.component(.weekday, from: date)
        if !habit.scheduledDays.isEmpty && !habit.scheduledDays.contains(weekday) {
            return .unscheduled
        }
        return .missed
    }

    private func allDayStatus(_ date: Date) -> DayStatus {
        if date > Date() { return .future }
        guard !appState.habits.isEmpty else { return .unscheduled }

        let weekday = cal.component(.weekday, from: date)

        // Only consider habits scheduled on this weekday
        let scheduledHabits = appState.habits.filter { habit in
            habit.scheduledDays.isEmpty || habit.scheduledDays.contains(weekday)
        }
        guard !scheduledHabits.isEmpty else { return .unscheduled }

        let completedCount = scheduledHabits.filter { habit in
            appState.logs.contains {
                $0.habitId == habit.id &&
                $0.completed &&
                cal.isDate($0.date, inSameDayAs: date)
            }
        }.count

        if completedCount == 0 { return .missed }
        if completedCount == scheduledHabits.count { return .completed }
        return .partial
    }

    private func cellColor(_ status: DayStatus) -> Color {
        switch status {
        case .completed:   return Theme.sage.opacity(0.85)
        case .partial:     return Color.orange.opacity(0.55)
        case .missed:      return Theme.terracotta.opacity(0.25)
        case .future:      return Color.clear
        case .unscheduled: return Color.clear
        }
    }

    private func cellTextColor(_ status: DayStatus) -> Color {
        switch status {
        case .completed:   return Theme.white
        case .partial:     return .white
        case .missed:      return Theme.terracotta
        case .future:      return Theme.primary
        case .unscheduled: return Theme.textSecondary
        }
    }

    // MARK: - Stats

    private func statsCard(habit: Habit) -> some View {
        let monthLogs = appState.logsFor(habit: habit, in: displayMonth)
        let completedCount = monthLogs.filter { $0.completed }.count
        let totalScheduled = monthLogs.count
        let rate = totalScheduled > 0 ? Int(Double(completedCount) / Double(totalScheduled) * 100) : 0

        return HabitCard {
            HStack(spacing: 0) {
                statItem(icon: "flame.fill", color: Theme.terracotta, value: "\(habit.streak)", label: "Streak")
                Divider().frame(height: 40)
                statItem(icon: "checkmark.circle.fill", color: Theme.sage, value: "\(completedCount)", label: "Done")
                Divider().frame(height: 40)
                statItem(icon: "percent", color: Theme.primary, value: "\(rate)%", label: "Rate")
            }
        }
    }

    private var allStatsCard: some View {
        let totalHabits = appState.habits.count
        let completedToday = appState.habits.filter { appState.isCompleted(habit: $0) }.count
        let allLogs = appState.habits.flatMap { appState.logsFor(habit: $0, in: displayMonth) }
        let monthRate = allLogs.isEmpty ? 0 : Int(Double(allLogs.filter { $0.completed }.count) / Double(allLogs.count) * 100)

        return HabitCard {
            HStack(spacing: 0) {
                statItem(icon: "list.bullet", color: Theme.softBlue, value: "\(totalHabits)", label: "Habits")
                Divider().frame(height: 40)
                statItem(icon: "checkmark.circle.fill", color: Theme.sage, value: "\(completedToday)", label: "Today")
                Divider().frame(height: 40)
                statItem(icon: "percent", color: Theme.primary, value: "\(monthRate)%", label: "This Month")
            }
        }
    }

    @ViewBuilder
    private func statItem(icon: String, color: Color, value: String, label: String) -> some View {
        VStack(spacing: 4) {
            Image(systemName: icon).foregroundColor(color)
            Text(value).font(.headline).foregroundColor(Theme.primary)
            Text(label).font(.caption).foregroundColor(Theme.textSecondary)
        }
        .frame(maxWidth: .infinity)
    }

    // MARK: - Helpers

    private func shiftMonth(_ delta: Int) {
        if let newMonth = cal.date(byAdding: .month, value: delta, to: displayMonth) {
            displayMonth = newMonth
        }
    }
}

private let monthFormatter: DateFormatter = {
    let f = DateFormatter()
    f.dateFormat = "LLLL yyyy"
    return f
}()
