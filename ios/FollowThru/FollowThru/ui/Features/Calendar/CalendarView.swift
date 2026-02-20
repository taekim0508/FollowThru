import SwiftUI

struct CalendarView: View {
    @EnvironmentObject var appState: AppState
    @State private var displayMonth = Date()
    @State private var selectedHabit: Habit? = nil

    private let cal = Calendar.current
    private let columns = Array(repeating: GridItem(.flexible()), count: 7)
    private let weekdayHeaders = ["Su","Mo","Tu","We","Th","Fr","Sa"]

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {

                    // Habit picker
                    if !appState.habits.isEmpty {
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 8) {
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
                        // Weekday headers
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
                            ForEach(gridDays(), id: \.self) { date in
                                dayCell(date)
                            }
                        }
                        .padding(.horizontal)
                    }

                    // Stats
                    if let habit = selectedHabit {
                        statsCard(habit: habit)
                            .padding(.horizontal)
                    } else if appState.habits.isEmpty {
                        Text("Create a habit to see your calendar")
                            .font(.subheadline)
                            .foregroundColor(Theme.textSecondary)
                            .padding(.top, 40)
                    } else {
                        Text("Select a habit above to see details")
                            .font(.subheadline)
                            .foregroundColor(Theme.textSecondary)
                    }
                }
                .padding(.vertical)
            }
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("Calendar")
            .navigationBarTitleDisplayMode(.inline)
            .onAppear {
                if selectedHabit == nil { selectedHabit = appState.habits.first }
            }
            .onChange(of: appState.habits.count) { _ in
                if selectedHabit == nil { selectedHabit = appState.habits.first }
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

        // Pad to complete last row
        while days.count % 7 != 0 { days.append(nil) }
        return days
    }

    @ViewBuilder
    private func dayCell(_ date: Date?) -> some View {
        if let date = date {
            let status = dayStatus(date)
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

    private enum DayStatus { case completed, missed, future, unscheduled }

    private func dayStatus(_ date: Date) -> DayStatus {
        guard let habit = selectedHabit else { return .unscheduled }

        if date > Date() { return .future }

        let log = appState.logs.first {
            $0.habitId == habit.id && cal.isDate($0.date, inSameDayAs: date)
        }
        if let log = log { return log.completed ? .completed : .missed }

        // Check if this weekday was scheduled
        let weekday = cal.component(.weekday, from: date)
        if !habit.scheduledDays.isEmpty && !habit.scheduledDays.contains(weekday) {
            return .unscheduled
        }
        return .missed
    }

    private func cellColor(_ status: DayStatus) -> Color {
        switch status {
        case .completed:  return Theme.sage.opacity(0.85)
        case .missed:     return Theme.terracotta.opacity(0.25)
        case .future:     return Color.clear
        case .unscheduled: return Color.clear
        }
    }

    private func cellTextColor(_ status: DayStatus) -> Color {
        switch status {
        case .completed:  return Theme.white
        case .missed:     return Theme.terracotta
        case .future:     return Theme.textSecondary
        case .unscheduled: return Theme.lightGray
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
