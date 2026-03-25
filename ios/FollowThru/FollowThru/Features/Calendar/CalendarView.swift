import SwiftUI

struct CalendarView: View {
    @EnvironmentObject var appState: AppState
    @State private var displayMonth = Date()
    @State private var selectedHabit: Habit? = nil

    private let cal = Calendar.current
    private let columns = Array(repeating: GridItem(.flexible()), count: 7)
    private let weekdayHeaders = ["SUN","MON","TUE","WED","THU","FRI","SAT"]
    private let dayNames = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {

                    // habit picker
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 8) {
                            Button { selectedHabit = nil } label: {
                                Text("All")
                                    .font(.subheadline)
                                    .fontWeight(selectedHabit == nil ? .semibold : .regular)
                                    .padding(.horizontal, 14).padding(.vertical, 8)
                                    .background(selectedHabit == nil ? Theme.primary : Theme.offWhite)
                                    .foregroundColor(selectedHabit == nil ? Theme.white : Theme.textSecondary)
                                    .cornerRadius(20)
                            }

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
                                        .font(.subheadline)
                                        .fontWeight(selected ? .semibold : .regular)
                                        .padding(.horizontal, 14).padding(.vertical, 8)
                                        .background(selected ? Theme.primary : Theme.offWhite)
                                        .foregroundColor(selected ? Theme.white : Theme.textSecondary)
                                        .cornerRadius(20)
                                }
                            }
                        }
                        .padding(.horizontal)
                    }

                    // month navigation
                    HStack {
                        Button { shiftMonth(-1) } label: {
                            Image(systemName: "chevron.left")
                                .foregroundColor(Theme.primary).padding(8)
                        }
                        Spacer()
                        Text(displayMonth, formatter: monthFormatter)
                            .font(.headline).foregroundColor(Theme.primary)
                        Spacer()
                        Button { shiftMonth(1) } label: {
                            Image(systemName: "chevron.right")
                                .foregroundColor(Theme.primary).padding(8)
                        }
                    }
                    .padding(.horizontal)

                    // calendar grid
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

                    // stats
                    if let habit = selectedHabit {
                        singleHabitStats(habit)
                            .padding(.horizontal)
                    } else {
                        allHabitsStats
                            .padding(.horizontal)
                    }
                }
                .padding(.vertical)
            }
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("Calendar")
            .navigationBarTitleDisplayMode(.inline)
            .onChange(of: appState.habits.count) { _ in
                if let selected = selectedHabit,
                   !appState.habits.contains(where: { $0.id == selected.id }) {
                    selectedHabit = nil
                }
            }
        }
    }

    // MARK: - Grid

    private func gridDays() -> [Date?] {
        guard let monthStart = cal.date(
            from: cal.dateComponents([.year, .month], from: displayMonth)
        ),
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
            let dayNum = cal.component(.day, from: date)
            let isToday = cal.isDateInToday(date)
            let status = selectedHabit != nil
                ? singleDayStatus(date, habit: selectedHabit!)
                : allDayStatus(date)

            ZStack {
                Circle()
                    .fill(cellColor(status))
                    .frame(width: 34, height: 34)
                    .overlay(
                        Circle().strokeBorder(
                            isToday ? Theme.primary : Color.clear,
                            lineWidth: 2
                        )
                    )
                Text("\(dayNum)")
                    .font(.caption)
                    .fontWeight(isToday ? .bold : .regular)
                    .foregroundColor(cellTextColor(status))
            }
            .frame(height: 38)
        } else {
            Color.clear.frame(height: 38)
        }
    }

    // MARK: - Day Status

    private enum DayStatus {
        case completed, partial, missed, future, unscheduled
    }

    private func singleDayStatus(_ date: Date, habit: Habit) -> DayStatus {
        if date > Date() { return .future }

        // check if this day is scheduled for the habit
        let weekdayIndex = cal.component(.weekday, from: date) - 1
        let dayName = dayNames[weekdayIndex]
        guard habit.frequencyPattern.days.contains(dayName) else { return .unscheduled }

        // check today_complete for today, otherwise unscheduled (we don't have history yet)
        if cal.isDateInToday(date) {
            return habit.todayComplete ? .completed : .missed
        }

        // for past days we'd need completion history — mark as unscheduled for now
        // TODO: fetch completion history per habit for calendar view
        return .unscheduled
    }

    private func allDayStatus(_ date: Date) -> DayStatus {
        if date > Date() { return .future }
        guard !appState.habits.isEmpty else { return .unscheduled }

        let weekdayIndex = cal.component(.weekday, from: date) - 1
        let dayName = dayNames[weekdayIndex]

        let scheduledHabits = appState.habits.filter {
            $0.frequencyPattern.days.contains(dayName)
        }
        guard !scheduledHabits.isEmpty else { return .unscheduled }

        // for today we have live data
        if cal.isDateInToday(date) {
            let completedCount = scheduledHabits.filter { $0.todayComplete }.count
            if completedCount == 0 { return .missed }
            if completedCount == scheduledHabits.count { return .completed }
            return .partial
        }

        // TODO: fetch completion history for past days
        return .unscheduled
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

    private func singleHabitStats(_ habit: Habit) -> some View {
        HabitCard {
            HStack(spacing: 0) {
                statItem(
                    icon: "flame.fill",
                    color: Theme.terracotta,
                    value: "\(habit.currentStreak)",
                    label: "Streak"
                )
                Divider().frame(height: 40)
                statItem(
                    icon: "trophy.fill",
                    color: Theme.sage,
                    value: "\(habit.maxStreak)",
                    label: "Best"
                )
                Divider().frame(height: 40)
                statItem(
                    icon: habit.todayComplete ? "checkmark.circle.fill" : "circle",
                    color: habit.todayComplete ? Theme.sage : Theme.textSecondary,
                    value: habit.todayComplete ? "Done" : "Pending",
                    label: "Today"
                )
            }
        }
    }

    private var allHabitsStats: some View {
        let total = appState.habits.count
        let completedToday = appState.todaysHabits.filter { $0.todayComplete }.count
        let totalToday = appState.todaysHabits.count
        let bestStreak = appState.habits.map { $0.maxStreak }.max() ?? 0

        return HabitCard {
            HStack(spacing: 0) {
                statItem(icon: "list.bullet", color: Theme.softBlue,
                         value: "\(total)", label: "Habits")
                Divider().frame(height: 40)
                statItem(icon: "checkmark.circle.fill", color: Theme.sage,
                         value: "\(completedToday)/\(totalToday)", label: "Today")
                Divider().frame(height: 40)
                statItem(icon: "trophy.fill", color: Theme.terracotta,
                         value: "\(bestStreak)", label: "Best Streak")
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
